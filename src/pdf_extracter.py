import os
from dotenv import load_dotenv
import time
import requests
import re
from pathlib import Path
from src.markdown_cleaner import limpiar_markdown

load_dotenv()
MINERU_TOKEN = os.getenv("MINERU_API_KEY")
BASE_URL = "https://mineru.net/api/v4"

# Timeouts (segundos) — ajusta si tus PDFs son muy pesados
TIMEOUT_REQUEST = 20      # llamadas cortas: pedir URL, consultar estado
TIMEOUT_UPLOAD = 120      # subir el PDF puede pesar más
TIMEOUT_DOWNLOAD = 60     # descargar el zip de resultado

_RE_ATX = re.compile(r'^(#{1,6})\s*(.+?)\s*#*$')

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
    try:
        resp = requests.post(
            f"{BASE_URL}/file-urls/batch",
            headers=_get_headers(),
            json={
                "files": [{"name": filename, "data_id": filename}],
                "model_version": "pipeline",
                "language": "es",
                "enable_table": True,
                "is_ocr": True,
                "enable_formula": True
            },
            timeout=TIMEOUT_REQUEST
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"MinerU no respondió en {TIMEOUT_REQUEST}s al pedir URL de subida. "
            "El servicio puede estar caído o lento ahora mismo."
        )
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"No se pudo conectar con MinerU: {e}")

    resp.raise_for_status()
    result = resp.json()

    if result["code"] != 0:
        raise RuntimeError(f"MinerU error: {result['msg']}")

    batch_id = result["data"]["batch_id"]
    upload_url = result["data"]["file_urls"][0]
    print(f"[MinerU] batch_id: {batch_id}")

    # 2. Subir el PDF por PUT (sin Content-Type según la doc)
    try:
        put_resp = requests.put(upload_url, data=pdf_bytes, timeout=TIMEOUT_UPLOAD)
    except requests.exceptions.Timeout:
        raise RuntimeError(f"MinerU no respondió en {TIMEOUT_UPLOAD}s al subir el archivo.")

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
    errores_consecutivos = 0
    MAX_ERRORES_CONSECUTIVOS = 5  # si falla 5 veces seguidas, abortamos aunque quede presupuesto

    while time.time() - inicio < timeout:
        try:
            resp = requests.get(
                f"{BASE_URL}/extract-results/batch/{batch_id}",
                headers=_get_headers(),
                timeout=TIMEOUT_REQUEST  # ← clave: esto evita el cuelgue indefinido
            )
            resp.raise_for_status()
            resultados = resp.json()["data"]["extract_result"]
            errores_consecutivos = 0  # reset si esta llamada sí funcionó
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            errores_consecutivos += 1
            elapsed = int(time.time() - inicio)
            print(f"[MinerU] [{elapsed}s] ⚠️ Sin respuesta ({errores_consecutivos}/{MAX_ERRORES_CONSECUTIVOS}): {e}")
            if errores_consecutivos >= MAX_ERRORES_CONSECUTIVOS:
                raise RuntimeError(
                    f"MinerU dejó de responder tras {errores_consecutivos} intentos seguidos. "
                    "El servicio probablemente está caído."
                )
            time.sleep(interval)
            continue

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

    try:
        resp = requests.get(zip_url, timeout=TIMEOUT_DOWNLOAD)
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Timeout descargando el resultado de MinerU ({TIMEOUT_DOWNLOAD}s).")
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        # El MD principal siempre se llama full.md según la doc
        with z.open("full.md") as f:
            contenido_raw = f.read().decode("utf-8")

    return limpiar_markdown(contenido_raw)


def extraer_titulo(contenido: str, fallback: str) -> str:
    """
    Busca el título dentro del contenido ya extraído del documento.
    Soporta:
      - Encabezados ATX ('#', '##'...), con o sin espacio tras el '#'
      - Encabezados Setext ('Título' seguido de una línea de '===' o '---')
      - Frontmatter YAML inicial (se ignora al buscar)
    Prioriza el primer H1 encontrado; si no hay ninguno, usa el mejor
    nivel disponible (H2, H3...). Si no encuentra nada razonable, devuelve
    el fallback (normalmente el nombre del archivo sin extensión).
    """
    lineas = contenido.splitlines()

    inicio = 0
    if lineas and lineas[0].strip() == "---":
        for i in range(1, len(lineas)):
            if lineas[i].strip() == "---":
                inicio = i + 1
                break

    mejor_por_nivel: dict = {}

    i = inicio
    while i < len(lineas):
        if 1 in mejor_por_nivel:
            break

        linea = lineas[i].strip()
        if not linea:
            i += 1
            continue

        match = _RE_ATX.match(linea)
        if match:
            nivel = len(match.group(1))
            texto = match.group(2).strip()
            if texto and nivel not in mejor_por_nivel:
                mejor_por_nivel[nivel] = texto
            i += 1
            continue

        if i + 1 < len(lineas):
            siguiente = lineas[i + 1].strip()
            if siguiente and set(siguiente) == {"="} and len(siguiente) >= 3:
                mejor_por_nivel.setdefault(1, linea)
                i += 2
                continue
            if siguiente and set(siguiente) == {"-"} and len(siguiente) >= 3 and "|" not in linea:
                mejor_por_nivel.setdefault(2, linea)
                i += 2
                continue

        i += 1

    for nivel in sorted(mejor_por_nivel):
        return mejor_por_nivel[nivel]

    return fallback


# Prueba
if __name__ == "__main__":
    contenido = extract_pdf("data/pdfs/DE_U2_T1.pdf")
    print(contenido[:500])