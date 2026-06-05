#!/usr/bin/env python3
"""
Script para iniciar la API de AcademIA
Maneja instalación de dependencias y lanzamiento del servidor
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def instalar_dependencias():
    """Instala las dependencias necesarias"""
    print("📦 Instalando dependencias...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements-api.txt"],
            check=True
        )
        print("✅ Dependencias instaladas")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al instalar dependencias: {e}")
        sys.exit(1)

def validar_configuracion():
    """Valida que la configuración esté correcta"""
    print("\n🔍 Validando configuración...")
    
    # Verificar variables de entorno
    api_token = os.getenv("API_TOKEN")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    
    if not api_token or api_token == "tu_token_secreto_aqui_cambiar_en_produccion":
        print("⚠️  AVISO: API_TOKEN no está configurado correctamente en .env")
        print("   Usando valor por defecto: token_secreto_academia_ia_2024")
    else:
        print(f"✅ API_TOKEN configurado")
    
    if not openrouter_key:
        print("⚠️  AVISO: OPENROUTER_API_KEY no está configurado")
        print("   Algunos scripts de IA no funcionarán")
    else:
        print(f"✅ OPENROUTER_API_KEY configurado")
    
    # Verificar carpetas necesarias
    carpetas = ["data/pdfs", "markdowns", "Obsidian_Vault"]
    for carpeta in carpetas:
        Path(carpeta).mkdir(parents=True, exist_ok=True)
        print(f"✅ Carpeta verificada: {carpeta}")

def mostrar_info():
    """Muestra información de la API"""
    print("\n" + "="*50)
    print("🚀 AcademIA API - Iniciando")
    print("="*50)
    
    port = os.getenv("PORT", "8000")
    api_token = os.getenv("API_TOKEN", "token_secreto_academia_ia_2024")
    
    print(f"\n📍 URL Base:    http://localhost:{port}")
    print(f"📚 Docs:        http://localhost:{port}/docs")
    print(f"🔐 Token:       {api_token}")
    print(f"🔄 WebSocket:   ws://localhost:{port}/ws")
    
    print("\n" + "-"*50)
    print("Endpoints disponibles:")
    print("  • GET  /health           - Estado del servidor")
    print("  • POST /process_pdf      - Procesar PDF")
    print("  • POST /save_note        - Guardar nota")
    print("  • WS   /ws               - WebSocket")
    print("-"*50 + "\n")

def iniciar_api():
    """Inicia el servidor FastAPI"""
    print("▶️  Iniciando servidor...")
    
    try:
        import uvicorn
        import api  # Importar el módulo para verificar que existe
        
        port = int(os.getenv("PORT", 8000))
        debug = os.getenv("DEBUG", "False").lower() == "true"
        
        uvicorn.run(
            "api:app",
            host="0.0.0.0",
            port=port,
            reload=debug
        )
    except ImportError as e:
        print(f"❌ Error al importar módulos: {e}")
        print("   Ejecuta: pip install -r requirements-api.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error al iniciar API: {e}")
        sys.exit(1)

def main():
    """Función principal"""
    print("\n🎓 AcademIA API Setup\n")
    
    # Parsear argumentos
    args = sys.argv[1:]
    
    if "--help" in args or "-h" in args:
        print("Uso: python start_api.py [opciones]\n")
        print("Opciones:")
        print("  --install    Instalar/actualizar dependencias")
        print("  --check      Solo verificar configuración")
        print("  --help       Mostrar esta ayuda")
        print()
        return
    
    # Instalar dependencias si se solicita
    if "--install" in args:
        instalar_dependencias()
        return
    
    # Validar configuración
    validar_configuracion()
    
    # Solo verificar si se solicita
    if "--check" in args:
        print("✅ Configuración válida\n")
        return
    
    # Mostrar información
    mostrar_info()
    
    # Iniciar API
    iniciar_api()

if __name__ == "__main__":
    main()
