import os
from dotenv import load_dotenv
import time
import requests
from pathlib import Path
from src.markdown_cleaner import limpiar_markdown

load_dotenv()
MINERU_TOKEN = os.getenv("MINERU_API_KEY")
BASE_URL = "https://mineru.net/api/v4"
def _get_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('MINERU_API_KEY')}"
    }

def extract_pdf(ruta_pdf: str) -> str:
    """
    Extrae el contenido de un PDF a Markdown usando la API v4 de MinerU.
    Lee el archivo, obtiene los bytes y llama a extract_pdf_from_bytes.
    """
    ruta = Path(ruta_pdf)
    pdf_bytes = ruta.read_bytes()
    return extract_pdf_from_bytes(pdf_bytes, ruta.name)

def extract_pdf_from_bytes(pdf_bytes: bytes, filename: str) -> str:
    """
    Extrae Markdown desde bytes de un PDF usando la API v4 de MinerU con token.
    Flujo: obtener URL firmada → subir PDF → polling → descargar MD
    """
    print(f"[MinerU] Obteniendo URL de subida para: {filename}")

    # 1. Pedir URL firmada de subida
    resp = requests.post(
        f"{BASE_URL}/file-urls/batch",
        headers=_get_headers(),
        json={
            "files": [{"name": filename, "data_id": filename}],
            "model_version": "vlm",
            "language": "es",
            "enable_table": True,
            "is_ocr": True,
            "enable_formula": True
        }
    )
    resp.raise_for_status()
    result = resp.json()

    if result["code"] != 0:
        raise RuntimeError(f"MinerU error: {result['msg']}")

    batch_id = result["data"]["batch_id"]
    upload_url = result["data"]["file_urls"][0]
    print(f"[MinerU] batch_id: {batch_id}")

    # 2. Subir el PDF por PUT (sin Content-Type según la doc)
    put_resp = requests.put(upload_url, data=pdf_bytes)
    if put_resp.status_code not in (200, 201):
        raise RuntimeError(f"MinerU fallo al subir: HTTP {put_resp.status_code}")
    print("[MinerU] Archivo subido, esperando resultado...")

    # 3. Polling por batch
    return _poll_batch(batch_id)


def _poll_batch(batch_id: str, timeout: int = 300, interval: int = 5) -> str:
    estados = {
        "waiting-file": "esperando archivo",
        "pending": "en cola",
        "running": "procesando",
        "converting": "convirtiendo"
    }
    inicio = time.time()

    while time.time() - inicio < timeout:
        resp = requests.get(
            f"{BASE_URL}/extract-results/batch/{batch_id}",
            headers=_get_headers()
        )
        resp.raise_for_status()
        resultados = resp.json()["data"]["extract_result"]
        tarea = resultados[0]
        estado = tarea["state"]
        elapsed = int(time.time() - inicio)

        if estado == "done":
            zip_url = tarea["full_zip_url"]
            print(f"[MinerU] ✅ Listo en {elapsed}s, descargando MD...")
            return _extraer_md_del_zip(zip_url)

        if estado == "failed":
            raise RuntimeError(f"MinerU falló: {tarea.get('err_msg', 'error desconocido')}")

        print(f"[MinerU] [{elapsed}s] {estados.get(estado, estado)}...")
        time.sleep(interval)

    raise TimeoutError(f"MinerU timeout en {timeout}s. batch_id: {batch_id}")


def _extraer_md_del_zip(zip_url: str) -> str:
    """Descarga el zip y extrae el full.md"""
    import zipfile
    import io

    resp = requests.get(zip_url)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        # El MD principal siempre se llama full.md según la doc
        with z.open("full.md") as f:
            contenido_raw = f.read().decode("utf-8")

    return limpiar_markdown(contenido_raw)

def extraer_titulo(contenido: str, fallback: str) -> str:
    """
    Busca el primer encabezado H1 (# ) dentro del contenido ya extraído
    del documento y lo usa como título real. Si no encuentra ninguno,
    devuelve el fallback (normalmente el nombre del archivo sin extensión).
    """
    if not contenido:
        return fallback

    for linea in contenido.splitlines():
        linea = linea.strip()
        if linea.startswith("# "):
            titulo = linea[2:].strip()
            if titulo:
                return titulo
    return fallback

# Prueba
if __name__ == "__main__":
    contenido = extract_pdf("data/pdfs/DE_U2_T1.pdf")
    print(contenido[:500])