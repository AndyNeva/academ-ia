import os
import json
import asyncio
import uuid
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.doc_extracter import extract_file
from src.ai_processor import process_document
from src.obsidian_exporter import (
    guardar_fuente, set_ws_manager, init_db, eliminar_del_indice
)
from src.background_tasks import run_background_task, get_task_status, cleanup_task

load_dotenv()

# ─────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────

API_TOKEN = os.getenv("API_TOKEN", "tu_token_secreto_aqui")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
FORMATOS_SOPORTADOS = {".pdf", ".pptx", ".docx"}

app = FastAPI(
    title="AcademIA API",
    description="Procesa PDFs, PPTX y DOCX y genera notas Zettelkasten",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────
# WebSocket Manager
# ─────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    async def connect(self, cliente_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[cliente_id] = websocket
        print(f"✅ Plugin conectado: {cliente_id}")

    def disconnect(self, cliente_id: str):
        self.connections.pop(cliente_id, None)
        print(f"❌ Plugin desconectado: {cliente_id}")

    async def enviar(self, cliente_id: str, payload: dict):
        ws = self.connections.get(cliente_id)
        if not ws:
            raise RuntimeError(f"Plugin no conectado: {cliente_id}")
        await ws.send_json(payload)
        await asyncio.sleep(0.3)

    def esta_conectado(self, cliente_id: str) -> bool:
        return cliente_id in self.connections


manager = ConnectionManager()
set_ws_manager(manager)

# ─────────────────────────────────────────
# Startup
# ─────────────────────────────────────────

@app.on_event("startup")
async def startup():
    try:
        init_db()
        print("✅ Base de datos conectada")
    except Exception as e:
        print(f"⚠️ BD no disponible: {e}")


def validar_token(token: str) -> bool:
    return token == API_TOKEN

# ─────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/process_pdf")
async def process_file_endpoint(
    file: UploadFile = File(...),
    token: str = Query(None),
    cliente_id: str = Query(None),
    destino: str = Query("obsidian")  # "obsidian" | "pdf"
):
    """
    Procesa un documento (PDF, PPTX o DOCX) de forma asincronizada.
    
    Devuelve un task_id inmediatamente (202 Accepted).
    El procesamiento ocurre en background.
    
    - destino=obsidian: envía las notas al plugin de Obsidian por WebSocket
    - destino=pdf: devuelve un PDF con todas las notas (cuando termina)
    """
    if not validar_token(token):
        raise HTTPException(status_code=401, detail="Token inválido")

    if not cliente_id:
        raise HTTPException(status_code=400, detail="cliente_id requerido")

    # Validar formato
    ext = Path(file.filename).suffix.lower()
    if ext not in FORMATOS_SOPORTADOS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado: {ext}. Usa PDF, PPTX o DOCX."
        )

    # Para Obsidian, verificar que el plugin esté conectado
    if destino == "obsidian" and not manager.esta_conectado(cliente_id):
        raise HTTPException(
            status_code=400,
            detail="Plugin de Obsidian no conectado. Abre Obsidian primero."
        )

    try:
        file_bytes = await file.read()
        nombre = Path(file.filename).stem
        task_id = str(uuid.uuid4())
        
        print(f"📄 Tarea {task_id}: Procesando {ext.upper()}: {nombre} → destino: {destino}")

        # Crear función para procesar
        async def process_task():
            # 1. Extraer texto según el formato
            print(f"[{task_id}] 1/4 Extrayendo contenido...")
            contenido_crudo = extract_file(file_bytes, file.filename)

            # 2. Guardar fuente raw (solo si va a Obsidian)
            if destino == "obsidian":
                print(f"[{task_id}] 2/4 Guardando fuente...")
                await guardar_fuente(contenido_crudo, nombre, cliente_id)
            else:
                print(f"[{task_id}] 2/4 Saltando fuente (destino PDF)...")

            # 3. Procesar con IA (AQUÍ es donde puede fallar por modelo)
            print(f"[{task_id}] 3/4 Procesando con IA...")
            resultado = await process_document(
                contenido_crudo,
                filename=nombre,
                cliente_id=cliente_id,
                destino=destino
            )

            # 4. Si destino es PDF, generar archivo
            if destino == "pdf":
                pdf_bytes = resultado.get("pdf_bytes")
                if not pdf_bytes:
                    raise RuntimeError("Error generando PDF")
                print(f"[{task_id}] 4/4 ✅ PDF listo: {len(pdf_bytes)} bytes")
            else:
                print(f"[{task_id}] 4/4 ✅ Notas enviadas a Obsidian\")\n            \n            return resultado

        # Lanzar tarea en background\n        asyncio.create_task(\n            run_background_task(\n                task_id=task_id,\n                cliente_id=cliente_id,\n                task_func=process_task,\n                ws_manager=manager\n            )\n        )\n        \n        # Retornar inmediatamente con 202 Accepted\n        return {\n            \"status\": \"accepted\",\n            \"task_id\": task_id,\n            \"mensaje\": \"📄 Documento en procesamiento. Recibirás una notificación cuando esté listo.\",\n            \"nombre\": nombre,\n            \"formato\": ext,\n            \"destino\": destino\n        }\n\n    except Exception as e:\n        print(f\"❌ Error en validación: {e}\")\n        raise HTTPException(status_code=500, detail=str(e))\n\n\n@app.get(\"/task/{task_id}\")\nasync def get_task_endpoint(task_id: str):\n    \"\"\"\n    Obtiene el estado de una tarea en procesamiento.\n    \"\"\"\n    status = get_task_status(task_id)\n    if not status:\n        raise HTTPException(status_code=404, detail=\"Tarea no encontrada\")\n    return status\n\n\n@app.delete(\"/task/{task_id}\")\nasync def cleanup_task_endpoint(task_id: str):\n    \"\"\"\n    Limpia una tarea completada del registro.\n    \"\"\"\n    cleanup_task(task_id)\n    return {\"status\": \"ok\", \"mensaje\": \"Tarea limpiada\"}\n\n# ─────────────────────────────────────────\n# WebSocket\n# ─────────────────────────────────────────\n\n@app.websocket(\"/ws\")\nasync def websocket_endpoint(websocket: WebSocket):\n    await websocket.accept()\n    cliente_id = None\n\n    try:\n        while True:\n            data = await websocket.receive_json()\n\n            if data.get(\"type\") == \"auth\":\n                token = data.get(\"token\")\n                user_id = data.get(\"user_id\")\n\n                if not user_id:\n                    await websocket.send_json({\n                        \"type\": \"auth\", \"success\": False,\n                        \"error\": \"user_id requerido\"\n                    })\n                    continue\n\n                if validar_token(token):\n                    cliente_id = str(user_id)\n                    manager.connections[cliente_id] = websocket\n                    await websocket.send_json({\n                        \"type\": \"auth\", \"success\": True,\n                        \"cliente_id\": cliente_id,\n                        \"mensaje\": f\"Conectado como {cliente_id}\"\n                    })\n                    print(f\"✅ Autenticado: {cliente_id}\")\n                else:\n                    await websocket.send_json({\n                        \"type\": \"auth\", \"success\": False,\n                        \"error\": \"Token inválido\"\n                    })\n                    await websocket.close(code=1008)\n                    break\n\n            elif data.get(\"type\") == \"delete_atomica\":\n                if cliente_id:\n                    nombre = data.get(\"nombre\", \"\")\n                    eliminar_del_indice(nombre, cliente_id)\n\n            elif data.get(\"ok\") is not None:\n                print(f\"✅ Plugin confirmó: {data.get('nombre')}\")\n\n    except WebSocketDisconnect:\n        if cliente_id:\n            manager.disconnect(cliente_id)\n    except Exception as e:\n        print(f\"❌ Error WebSocket: {e}\")\n        if cliente_id:\n            manager.disconnect(cliente_id)\n\n\nif __name__ == \"__main__\":\n    port = int(os.getenv(\"PORT\", 8000))\n    uvicorn.run(\"api:app\", host=\"0.0.0.0\", port=port, reload=DEBUG)

