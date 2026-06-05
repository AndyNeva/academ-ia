import os
import json
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Importar funciones de tus scripts
from src.pdf_extracter import extract_pdf
from src.ai_processor import process_document
from src.obsidian_exporter import guardar_fuente, guardar_literatura, guardar_atomica, guardar_moc

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
# Modelos de Datos
# ─────────────────────────────────────────

class NotePayload:
    """Estructura para recibir notas"""
    def __init__(self, tipo: str, nombre: str, contenido: str, materia: Optional[str] = None):
        self.tipo = tipo
        self.nombre = nombre
        self.contenido = contenido
        self.materia = materia

# ─────────────────────────────────────────
# Validación de Token
# ─────────────────────────────────────────

def validar_token(token: str) -> bool:
    """Valida el token de autenticación"""
    return token == API_TOKEN

# ─────────────────────────────────────────
# WebSocket Manager
# ─────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    async def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting: {e}")

manager = ConnectionManager()

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
    token: str = None
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
    
    try:
        # Guardar archivo temporal
        temp_path = Path("data/pdfs") / file.filename
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Procesar PDF
        nombre = temp_path.stem
        print(f"📄 Procesando PDF: {nombre}")
        
        # Paso 1: Extraer
        print("1/3 Extrayendo con MinerU...")
        contenido_crudo = extract_pdf(str(temp_path))
        
        # Paso 2: Guardar fuente
        print("2/3 Guardando fuente...")
        guardar_fuente(contenido_crudo, nombre)
        
        # Paso 3: IA
        print("3/3 Procesando con IA...")
        resultado_ia = process_document(contenido_crudo, filename=nombre)
        
        return {
            "status": "success",
            "nombre": nombre,
            "mensaje": "PDF procesado correctamente",
            "resultado": resultado_ia
        }
    
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/save_note", tags=["Notes"])
async def save_note_endpoint(
    tipo: str,
    nombre: str,
    contenido: str,
    materia: Optional[str] = None,
    token: str = None
):
    """
    Guarda una nota directamente en Obsidian.
    tipos: "literatura", "atomica", "moc"
    """
    # Validar token
    if not token or not validar_token(token):
        raise HTTPException(status_code=401, detail="Token inválido")
    
    try:
        if tipo.lower() == "literatura":
            guardar_literatura(contenido, nombre, materia or "General")
        elif tipo.lower() == "atomica":
            guardar_atomica(contenido, nombre, materia or "General")
        elif tipo.lower() == "moc":
            guardar_moc(contenido, nombre, materia or "General")
        else:
            raise ValueError(f"Tipo de nota inválido: {tipo}")
        
        return {
            "status": "success",
            "tipo": tipo,
            "nombre": nombre,
            "mensaje": "Nota guardada correctamente"
        }
    
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────
# WebSocket Endpoint
# ─────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para comunicación con Obsidian plugin.
    
    Flujo:
    1. Cliente envía: {"type": "auth", "token": "..."}
    2. Servidor valida y responde: {"type": "auth", "success": true/false}
    3. Cliente envía notas: {"tipo": "...", "nombre": "...", "contenido": "...", "materia": "..."}
    4. Servidor procesa y responde: {"ok": true/false, "nombre": "...", "error": "..."}
    """
    await manager.connect(websocket)
    authenticated = False
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Mensaje de autenticación
            if data.get("type") == "auth":
                token = data.get("token")
                if validar_token(token):
                    authenticated = True
                    await websocket.send_json({
                        "type": "auth",
                        "success": True,
                        "mensaje": "Autenticación exitosa"
                    })
                    print(f"✅ WebSocket autenticado")
                else:
                    await websocket.send_json({
                        "type": "auth",
                        "success": False,
                        "error": "Token inválido"
                    })
                    await websocket.close(code=1008)
            
            # Procesar notas solo si está autenticado
            elif authenticated:
                try:
                    tipo = data.get("tipo")
                    nombre = data.get("nombre")
                    contenido = data.get("contenido")
                    materia = data.get("materia", "General")
                    
                    # Validar datos
                    if not all([tipo, nombre, contenido]):
                        await websocket.send_json({
                            "ok": False,
                            "error": "Faltan campos requeridos: tipo, nombre, contenido"
                        })
                        continue
                    
                    # Guardar nota
                    if tipo.lower() == "literatura":
                        guardar_literatura(contenido, nombre, materia)
                    elif tipo.lower() == "atomica":
                        guardar_atomica(contenido, nombre, materia)
                    elif tipo.lower() == "moc":
                        guardar_moc(contenido, nombre, materia)
                    else:
                        raise ValueError(f"Tipo inválido: {tipo}")
                    
                    print(f"✅ Nota guardada: {tipo} - {nombre}")
                    
                    # Confirmar al cliente
                    await websocket.send_json({
                        "ok": True,
                        "nombre": nombre,
                        "tipo": tipo,
                        "mensaje": "Nota guardada exitosamente"
                    })
                
                except Exception as e:
                    print(f"❌ Error al guardar nota: {e}")
                    await websocket.send_json({
                        "ok": False,
                        "error": str(e)
                    })
            
            else:
                await websocket.send_json({
                    "ok": False,
                    "error": "No autenticado. Envía tu token primero."
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("❌ WebSocket desconectado")
    except Exception as e:
        print(f"❌ Error WebSocket: {e}")
        manager.disconnect(websocket)

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
