from pathlib import Path
import json
import re

VAULT_PATH = Path("D:/Obsidian/Proyectos/AcademicAI")
INDEX_PATH = VAULT_PATH / ".obsidian" / "atomicas_index.json"

def guardar_fuente(contenido: str, nombre: str) -> Path:
    """Guarda el markdown crudo de MinerU en la carpeta Fuentes."""
    carpeta = VAULT_PATH / "Fuentes"
    
    ruta = carpeta / f"{nombre}.md"
    
    # Agregar metadatos al inicio (frontmatter de Obsidian)
    frontmatter = f"""---
tipo: fuente-cruda
origen: pdf
archivo: {nombre}.pdf
procesado: {__import__('datetime').date.today()}
---

"""
    ruta.write_text(frontmatter + contenido, encoding="utf-8")
    print(f"✅ Fuente guardada: {ruta}")
    return ruta


def guardar_literatura(contenido_llm: str, nombre: str, fuente: str) -> Path:
    carpeta = VAULT_PATH / "Literatura"
    carpeta.mkdir(parents=True, exist_ok=True)
    
    ruta = carpeta / f"{nombre}_lit.md"
    footer = f"\n\n---\n📄 Fuente: [[Fuentes/{fuente}]]\n"
    
    ruta.write_text(contenido_llm + footer, encoding="utf-8")
    print(f"✅ Literatura guardada: {ruta}")
    return ruta


def guardar_atomica(contenido_llm: str, nombre: str, fuente: str) -> Path:
    carpeta = VAULT_PATH / "Atomicas"
    carpeta.mkdir(parents=True, exist_ok=True)
    
    # Nombre limpio para el archivo (sin caracteres problemáticos)
    nombre_archivo = nombre.replace("/", "-").replace(":", "").strip()
    ruta = carpeta / f"{nombre_archivo}.md"
    footer = f"\n\n---\n📄 Extraído de: [[Literatura/{fuente}_lit]]\n"
    
    ruta.write_text(contenido_llm + footer, encoding="utf-8")
    
    # Actualizar índice para deduplicación
    _actualizar_indice(nombre, contenido_llm)
    
    print(f"✅ Atómica guardada: {ruta}")
    return ruta


def guardar_moc(contenido_llm: str, materia: str, fuente: str) -> Path:
    carpeta = VAULT_PATH / "MOCs"
    carpeta.mkdir(parents=True, exist_ok=True)
    
    # El MOC se nombra por materia, no por documento
    # Si ya existe, se sobreescribe (el LLM ya integró el contenido previo)
    nombre_archivo = materia.replace("/", "-").replace(":", "").strip()
    ruta = carpeta / f"MOC_{nombre_archivo}.md"
    footer = f"\n\n---\n📄 Última actualización desde: [[Literatura/{fuente}_lit]]\n"
    
    ruta.write_text(contenido_llm + footer, encoding="utf-8")
    print(f"✅ MOC guardado: {ruta}")
    return ruta

def _actualizar_indice(nombre: str, contenido: str) -> None:
    index = _get_indice()
    aliases = _extraer_aliases(contenido)
    # Evitar duplicados en el propio índice
    if not any(n["nombre"] == nombre for n in index):
        index.append({"nombre": nombre, "aliases": aliases})
        INDEX_PATH.write_text(
            json.dumps(index, ensure_ascii=False, indent=2), 
            encoding="utf-8"
        )

def _get_indice() -> list[dict]:
    if not INDEX_PATH.exists():
        return []
    return json.loads(INDEX_PATH.read_text())

def get_notas_existentes() -> list[dict]:
    index = _get_indice()
    
    # Filtrar las que realmente existen en el vault
    validas = []
    for nota in index:
        nombre_archivo = nota["nombre"].replace("/", "-").replace(":", "").strip()
        ruta = VAULT_PATH / "Atomicas" / f"{nombre_archivo}.md"
        if ruta.exists():
            validas.append(nota)
    
    # Si hubo borrados, actualizar el índice
    if len(validas) < len(index):
        eliminadas = len(index) - len(validas)
        print(f"🧹 Índice limpiado: {eliminadas} notas eliminadas del registro")
        INDEX_PATH.write_text(
            json.dumps(validas, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    return validas


def _extraer_aliases(contenido: str) -> list[str]:
    """Parsea el frontmatter YAML para extraer aliases."""
    match = re.search(r"aliases:\s*\[([^\]]*)\]", contenido)
    if not match:
        return []
    raw = match.group(1)
    return [a.strip().strip('"').strip("'") for a in raw.split(",") if a.strip()]