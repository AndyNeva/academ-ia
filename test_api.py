"""
Ejemplos para probar la API de AcademIA
Ejecuta: python test_api.py
"""

import os

import requests
import json
import asyncio
import os
import websockets
from pathlib import Path

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"
TOKEN = os.getenv("API_TOKEN")  # Asegúrate de tener un token válido en .env

# ─────────────────────────────────────────
# 1. Probar Health Check
# ─────────────────────────────────────────

def test_health():
    """Prueba que la API esté funcionando"""
    print("\n📊 Probando Health Check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"✅ Status: {response.status_code}")
        print(f"   {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"❌ Error: {e}")

# ─────────────────────────────────────────
# 2. Probar Guardar Nota (REST)
# ─────────────────────────────────────────

def test_save_note():
    """Prueba guardar una nota via REST"""
    print("\n📝 Probando /save_note...")
    
    params = {
        "token": TOKEN,
        "tipo": "atomica",
        "nombre": "Prueba_API",
        "contenido": "# Nota de prueba\n\nEsta es una nota de prueba de la API.",
        "materia": "Testing"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/save_note", params=params)
        print(f"✅ Status: {response.status_code}")
        print(f"   {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"❌ Error: {e}")

# ─────────────────────────────────────────
# 3. Probar Procesar PDF
# ─────────────────────────────────────────

def test_process_pdf():
    """Prueba procesar un PDF"""
    print("\n📄 Probando /process_pdf...")
    
    # Verificar que exista un PDF de prueba
    pdf_path = Path("data/pdfs/DesarrolloLenguaje.pdf")
    if not pdf_path.exists():
        print(f"⚠️  No existe PDF de prueba en {pdf_path}")
        print("   Crea un PDF de prueba o salta este test")
        return
    
    try:
        with open(pdf_path, "rb") as f:
            files = {"file": f}
            params = {"token": TOKEN}
            
            print(f"   Procesando {pdf_path.name}...")
            response = requests.post(
                f"{BASE_URL}/process_pdf",
                files=files,
                params=params,
                timeout=300  # 5 minutos
            )
            
            print(f"✅ Status: {response.status_code}")
            print(f"   {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"❌ Error: {e}")

# ─────────────────────────────────────────
# 4. Probar WebSocket
# ─────────────────────────────────────────

async def test_websocket():
    """Prueba WebSocket"""
    print("\n🔌 Probando WebSocket...")
    
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("   ✅ Conectado a WebSocket")
            
            # Paso 1: Autenticar
            print("   1️⃣  Enviando autenticación...")
            await websocket.send(json.dumps({
                "type": "auth",
                "token": TOKEN
            }))
            
            response = await websocket.recv()
            auth_response = json.loads(response)
            print(f"      {auth_response}")
            
            if not auth_response.get("success"):
                print("❌ Autenticación fallida")
                return
            
            # Paso 2: Enviar nota
            print("   2️⃣  Enviando nota...")
            await websocket.send(json.dumps({
                "tipo": "literatura",
                "nombre": "Prueba_WebSocket",
                "contenido": "# Nota vía WebSocket\n\nPrueba de conexión WebSocket.",
                "materia": "Testing"
            }))
            
            response = await websocket.recv()
            note_response = json.loads(response)
            print(f"      {note_response}")
            
            if note_response.get("ok"):
                print("✅ Nota guardada exitosamente")
            else:
                print(f"❌ Error: {note_response.get('error')}")
    
    except Exception as e:
        print(f"❌ Error WebSocket: {e}")

# ─────────────────────────────────────────
# 5. Menú interactivo
# ─────────────────────────────────────────

def menu():
    """Menú para seleccionar qué probar"""
    print("\n" + "="*50)
    print("🧪 Tests de API - AcademIA")
    print("="*50)
    print("\nAsegúrate de que la API esté corriendo:")
    print("   python api.py")
    print("\nOpciones:")
    print("  1. Health Check")
    print("  2. Guardar Nota (REST)")
    print("  3. Procesar PDF")
    print("  4. WebSocket")
    print("  5. Ejecutar todos los tests")
    print("  0. Salir")
    print("-"*50)
    
    while True:
        try:
            opcion = input("\nSelecciona una opción (0-5): ").strip()
            
            if opcion == "0":
                print("\n👋 ¡Hasta luego!")
                break
            elif opcion == "1":
                test_health()
            elif opcion == "2":
                test_save_note()
            elif opcion == "3":
                test_process_pdf()
            elif opcion == "4":
                asyncio.run(test_websocket())
            elif opcion == "5":
                test_health()
                test_save_note()
                test_process_pdf()
                asyncio.run(test_websocket())
            else:
                print("❌ Opción no válida")
        
        except KeyboardInterrupt:
            print("\n\n👋 Interrumpido por el usuario")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

# ─────────────────────────────────────────
# Ejecutar
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Modo command-line
        if sys.argv[1] == "health":
            test_health()
        elif sys.argv[1] == "note":
            test_save_note()
        elif sys.argv[1] == "pdf":
            test_process_pdf()
        elif sys.argv[1] == "ws":
            asyncio.run(test_websocket())
        elif sys.argv[1] == "all":
            test_health()
            test_save_note()
            test_process_pdf()
            asyncio.run(test_websocket())
        else:
            print("Uso: python test_api.py [health|note|pdf|ws|all]")
    else:
        # Modo interactivo
        menu()
