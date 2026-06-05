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

# Importar funciones de tus scripts
from src.pdf_extracter import extract_pdf
from src.ai_processor import process_document
from src.obsidian_exporter import guardar_fuente, guardar_literatura, guardar_atomica, guardar_moc, set_ws_manager
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

# CORS configuración
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
        await asyncio.sleep(0.3)  # pausa para no saturar

    def esta_conectado(self, cliente_id: str) -> bool:
        return cliente_id in self.connections

manager = ConnectionManager()
set_ws_manager(manager)  # Inyectar el manager en obsidian_exporter

# ─────────────────────────────────────────
# Validación de Token
# ─────────────────────────────────────────

def validar_token(token: str) -> bool:
    """Valida el token de autenticación"""
    return token == API_TOKEN

# ─────────────────────────────────────────
# REST Endpoints
# ─────────────────────────────────────────

@app.get("/", tags=["Info"])
async def root():
    """Información de la API"""
    return {
        "nombre": "AcademIA API",
        "descripcion": "API para procesar PDFs y generar notas en Obsidian",
        "endpoints": {
            "health": "GET /health",
            "process_pdf": "POST /process_pdf",
            "save_note": "POST /save_note",
            "websocket": "WS /ws"
        }
    }

@app.get("/health", tags=["Info"])
async def health_check():
    """Verifica que la API esté funcionando"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/process_pdf", tags=["PDF"])
async def process_pdf_endpoint(
    file: UploadFile = File(...),
    token: str = Query(None),
    cliente_id: str = Query(None)
):
    """
    Procesa un PDF completo:
    1. Extrae contenido con MinerU
    2. Genera nota de literatura con IA
    3. Genera notas atómicas
    4. Genera MOCs
    """
    # Validar token
    if not token or not validar_token(token):
        raise HTTPException(status_code=401, detail="Token inválido")
    if not cliente_id:
        raise HTTPException(status_code=400, detail="cliente_id requerido")

    if not manager.esta_conectado(cliente_id):
        raise HTTPException(status_code=400, detail="Plugin de Obsidian no conectado")

    try:
        # Guardar archivo temporal
        temp_path = Path("data/pdfs") / file.filename
        nombre = temp_path.stem
        print(f"📄 Procesando PDF: {nombre}")
        
        # Paso 1: Extraer
        print("1/3 Extrayendo con MinerU...")
        contenido_crudo = extract_pdf(str(temp_path))
        
        # Paso 2: Guardar fuente
        print("2/3 Guardando fuente...")
        await guardar_fuente(contenido_crudo, nombre, cliente_id)
        
        # Paso 3: IA
        print("3/3 Procesando con IA...")
        resultado_ia = await process_document(contenido_crudo, filename=nombre, cliente_id=cliente_id)
        
        return {
            "status": "success",
            "nombre": nombre,
            "mensaje": "PDF procesado correctamente",
            "resultado": resultado_ia
        }
    
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────
# WebSocket Endpoint
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
                user_id = data.get("user_id", str(id(websocket)))

                if validar_token(token):
                    cliente_id = user_id
                    manager.connections[cliente_id] = websocket
                    await websocket.send_json({
                        "type": "auth",
                        "success": True,
                        "cliente_id": cliente_id
                    })
                    print(f"✅ Autenticado: {cliente_id}")
                else:
                    await websocket.send_json({
                        "type": "auth",
                        "success": False,
                        "error": "Token inválido"
                    })

            # El plugin confirma recepción de notas
            elif data.get("ok") is not None:
                print(f"Plugin confirmó: {data.get('nombre')}")

    except WebSocketDisconnect:
        if cliente_id:
            manager.disconnect(cliente_id)
    except Exception as e:
        print(f"❌ Error WebSocket: {e}")
        if cliente_id:
            manager.disconnect(cliente_id)

# ─────────────────────────────────────────
# Lanzar servidor
# ─────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"\n🚀 Iniciando API en http://localhost:{port}")
    print(f"📚 Documentación: http://localhost:{port}/docs")
    print(f"🔐 Token: {API_TOKEN}")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=port,
        reload=DEBUG
    )
