import os
import json
import asyncio
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
from src.doc_extracter import extract_file
from src.pdf_extracter import extraer_titulo

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
    Procesa un documento (PDF, PPTX o DOCX).

    - destino=obsidian: envía las notas al plugin de Obsidian por WebSocket
    - destino=pdf: devuelve un PDF con todas las notas para enviar por Telegram
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
        nombre_archivo = Path(file.filename).stem
        print(f"📄 Procesando {ext.upper()}: {nombre_archivo} → destino: {destino}")

        # 1. Extraer texto según el formato
        print("1/4 Extrayendo contenido...")
        try:
            contenido_crudo = extract_file(file_bytes, file.filename)
        except Exception as e:
            print(f"❌ Error extrayendo contenido de {file.filename}: {e}")
            raise HTTPException(
                status_code=422,
                detail=f"No se pudo extraer contenido del archivo: {e}"
            )

        if not contenido_crudo:
            raise HTTPException(
                status_code=422,
                detail=f"La extracción de {file.filename} no produjo contenido."
            )

        # Usar el título real encontrado dentro del documento,
        # en vez del nombre del archivo, para el resto del flujo
        nombre = extraer_titulo(contenido_crudo, fallback=nombre_archivo)
        print(f"📌 Título detectado: {nombre}")

        # 2. Guardar fuente raw (solo si va a Obsidian)
        if destino == "obsidian":
            print("2/4 Guardando fuente...")
            await guardar_fuente(contenido_crudo, nombre, cliente_id)
        else:
            print("2/4 Saltando fuente (destino PDF)...")

        # 3. Procesar con IA
        print("3/4 Procesando con IA...")
        resultado = await process_document(
            contenido_crudo,
            filename=nombre,
            cliente_id=cliente_id,
            destino=destino
        )

        # 4. Si destino es PDF, devolverlo como archivo
        if destino == "pdf":
            pdf_bytes = resultado.get("pdf_bytes")
            if not pdf_bytes:
                raise HTTPException(status_code=500, detail="Error generando PDF")

            print(f"4/4 ✅ PDF listo: {len(pdf_bytes)} bytes")
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{nombre}_notas.pdf"'
                }
            )

        print("4/4 ✅ Notas enviadas a Obsidian")
        return {
            "status": "success",
            "nombre": nombre,
            "formato": ext,
            "destino": destino,
            "atomicas_creadas": len(resultado.get("atomicas", [])),
            "fusiones": len(resultado.get("fusiones", [])),
            "mensaje": "Documento procesado correctamente"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    cliente_id = None

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "auth":
                token = data.get("token")
                user_id = data.get("user_id")

                if not user_id:
                    await websocket.send_json({
                        "type": "auth", "success": False,
                        "error": "user_id requerido"
                    })
                    continue

                if validar_token(token):
                    cliente_id = str(user_id)
                    manager.connections[cliente_id] = websocket
                    await websocket.send_json({
                        "type": "auth", "success": True,
                        "cliente_id": cliente_id,
                        "mensaje": f"Conectado como {cliente_id}"
                    })
                    print(f"✅ Autenticado: {cliente_id}")
                else:
                    await websocket.send_json({
                        "type": "auth", "success": False,
                        "error": "Token inválido"
                    })
                    await websocket.close(code=1008)
                    break

            elif data.get("type") == "delete_atomica":
                if cliente_id:
                    nombre = data.get("nombre", "")
                    eliminar_del_indice(nombre, cliente_id)

            elif data.get("ok") is not None:
                print(f"✅ Plugin confirmó: {data.get('nombre')}")

    except WebSocketDisconnect:
        if cliente_id:
            manager.disconnect(cliente_id)
    except Exception as e:
        print(f"❌ Error WebSocket: {e}")
        if cliente_id:
            manager.disconnect(cliente_id)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=DEBUG)