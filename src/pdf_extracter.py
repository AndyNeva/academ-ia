import shutil
import subprocess
from pathlib import Path
from src.markdown_cleaner import limpiar_markdown

def extract_pdf(ruta_pdf: str) -> str:
    """
    Extrae el contenido de un PDF a Markdown usando MinerU directamente.
    No necesita servidor corriendo.
    """
    carpeta_salida = Path("markdowns")


    print(f"Procesando {ruta_pdf}...")

    resultado = subprocess.run(
        [
            "mineru",
            "-p", ruta_pdf,
            "-o", str(carpeta_salida),
            "-b", "pipeline"   # corre en CPU, sin GPU
        ],
        capture_output=True,
        text=True
    )

    if resultado.returncode != 0:
        print("Error de MinerU:")
        print(resultado.stderr)
        raise RuntimeError("MinerU falló")

    # Buscar el .md generado
    archivos_md = list(carpeta_salida.rglob("*.md"))
    if not archivos_md:
        raise FileNotFoundError("MinerU no generó ningún archivo .md")
    
    ruta_md = archivos_md[0]
    contenido_raw = ruta_md.read_text(encoding="utf-8")
    contenido_limpio = limpiar_markdown(contenido_raw)

    # Borrar toda la carpeta de salida excepto guardar el .md limpio
    carpeta_doc = ruta_md.parent.parent  # carpeta DE_U2_T1/auto
    shutil.rmtree(carpeta_doc)           # borra todo

    print(f"✅ Markdown generado en: {ruta_md}")
    return contenido_limpio


# Prueba
if __name__ == "__main__":
    contenido = extract_pdf("data/pdfs/DE_U2_T1.pdf")
    print(contenido[:500])