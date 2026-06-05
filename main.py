import os
from pathlib import Path
from src.pdf_extracter import extract_pdf
from src.ai_processor import process_document
from src.obsidian_exporter import guardar_fuente

PDF_PATH = "data/pdfs/DesarrolloLenguaje.pdf"

def run_pipeline(ruta_pdf: str):
    nombre = Path(ruta_pdf).stem
    print(f"📄 Procesando: {nombre}")

    print("1/3 Extrayendo con MinerU...")
    contenido_crudo = extract_pdf(ruta_pdf)
    
    # Paso 2: Guardar fuente cruda en Obsidian
    print("2/3 Guardando fuente en Obsidian...")
    guardar_fuente(contenido_crudo, nombre)
    
    # Paso 3: Generar nota estructurada con LLM
    print("3/3 Generando nota estructurada...")
    ai_work = process_document(contenido_crudo, filename=nombre)


if __name__ == "__main__":
    run_pipeline(PDF_PATH)