import os
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.pdf_extracter import extract_pdf_from_bytes
from src.ai_processor import process_document
from src.obsidian_exporter import (
    guardar_fuente, set_ws_manager, init_db, eliminar_del_indice
)

load_dotenv()

# ─────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────

API_TOKEN = os.getenv("API_TOKEN", "tu_token_secreto_aqui")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

app = FastAPI(
    title="AcademIA API",
    description="API para procesar PDFs y generar notas en Obsidian",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────
# WebSocket Manager (por cliente_id)
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
# Inicializar BD al arrancar
# ─────────────────────────────────────────

@app.on_event("startup")
async def startup():
    init_db()
    print("🚀 AcademIA API lista")

# ─────────────────────────────────────────
# Validación de Token
# ─────────────────────────────────────────

def validar_token(token: str) -> bool:
    return token == API_TOKEN

# ─────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────

@app.get("/", tags=["Info"])
async def root():
    return {
        "nombre": "AcademIA API",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health",
            "process_pdf": "POST /process_pdf",
            "websocket": "WS /ws"
        }
    }

@app.get("/health", tags=["Info"])
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/process_pdf", tags=["PDF"])
async def process_pdf_endpoint(
    file: UploadFile = File(...),
    token: str = Query(None),
    cliente_id: str = Query(None)
):
    """
    Procesa un PDF completo:
    1. Extrae contenido con MinerU API
    2. Genera nota de literatura con IA
    3. Genera notas atómicas con deduplicación
    4. Genera MOC
    Todo se envía al plugin de Obsidian por WebSocket.
    """
    if not token or not validar_token(token):
        raise HTTPException(status_code=401, detail="Token inválido")

    if not cliente_id:
        raise HTTPException(status_code=400, detail="cliente_id requerido")

    if not manager.esta_conectado(cliente_id):
        raise HTTPException(status_code=400, detail="Plugin de Obsidian no conectado")

    try:
        pdf_bytes = await file.read()
        nombre = Path(file.filename).stem
        print(f"📄 Procesando PDF: {nombre} (usuario: {cliente_id})")

        # 1. Extraer con MinerU API (sin guardar en disco)
        print("1/4 Extrayendo con MinerU...")
        contenido_crudo = extract_pdf_from_bytes(pdf_bytes, file.filename)

        # 2. Guardar fuente raw en Obsidian
        print("2/4 Guardando fuente...")
        await guardar_fuente(contenido_crudo, nombre, cliente_id)

        # 3. Procesar con IA + deduplicación + enviar notas
        print("3/4 Procesando con IA...")
        resultado_ia = await process_document(
            contenido_crudo,
            filename=nombre,
            cliente_id=cliente_id
        )

        print("4/4 ✅ Completado")
        return {
            "status": "success",
            "nombre": nombre,
            "mensaje": "PDF procesado correctamente",
            "resultado": resultado_ia
        }

    except Exception as e:
        print(f"❌ Error procesando PDF: {e}")
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

            # ── Autenticación ──────────────────────────
            if data.get("type") == "auth":
                token = data.get("token")
                user_id = data.get("user_id")

                if not user_id:
                    await websocket.send_json({
                        "type": "auth",
                        "success": False,
                        "error": "user_id requerido"
                    })
                    continue

                if validar_token(token):
                    cliente_id = str(user_id)
                    manager.connections[cliente_id] = websocket
                    await websocket.send_json({
                        "type": "auth",
                        "success": True,
                        "cliente_id": cliente_id,
                        "mensaje": f"Conectado como {cliente_id}"
                    })
                    print(f"✅ Autenticado: {cliente_id}")
                else:
                    await websocket.send_json({
                        "type": "auth",
                        "success": False,
                        "error": "Token inválido"
                    })
                    await websocket.close(code=1008, reason="Token inválido")
                    break

            # ── Borrado de nota atómica ────────────────
            elif data.get("type") == "delete_atomica":
                if cliente_id:
                    nombre = data.get("nombre", "")
                    eliminar_del_indice(nombre, cliente_id)
                    print(f"🗑️ Borrado notificado: {nombre} (usuario: {cliente_id})")

            # ── Confirmación de nota guardada ──────────
            elif data.get("ok") is not None:
                nota_nombre = data.get("nombre", "")
                print(f"✅ Plugin confirmó: {nota_nombre}")

            else:
                print(f"⚠️ Mensaje desconocido: {data}")

    except WebSocketDisconnect:
        if cliente_id:
            manager.disconnect(cliente_id)
    except Exception as e:
        print(f"❌ Error WebSocket: {e}")
        if cliente_id:
            manager.disconnect(cliente_id)

# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"\n🚀 Iniciando API en http://localhost:{port}")
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=DEBUG)