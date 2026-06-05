from pathlib import Path
import json
import re

VAULT_PATH = Path("D:/Obsidian/Proyectos/AcademicAI")
INDEX_PATH = VAULT_PATH / ".obsidian" / "atomicas_index.json"

# Referencia al WebSocket manager (se inyecta desde api.py)
_ws_manager = None

def set_ws_manager(manager):
    """api.py llama esto al iniciar para inyectar el manager de WebSockets."""
    global _ws_manager
    _ws_manager = manager


async def _enviar_nota(tipo: str, nombre: str, contenido: str, cliente_id: str):
    """Envía la nota al plugin de Obsidian por WebSocket."""
    if _ws_manager is None:
        raise RuntimeError("WebSocket manager no configurado")
    await _ws_manager.enviar(cliente_id, {
        "tipo": tipo,
        "nombre": nombre,
        "contenido": contenido
    })


# ── Funciones públicas (ahora async) ──────────────────────────

async def guardar_fuente(contenido: str, nombre: str, cliente_id: str):
    frontmatter = f"""---
tipo: fuente-cruda
origen: pdf
archivo: {nombre}.pdf
procesado: {__import__('datetime').date.today()}
---

"""
    await _enviar_nota("fuente", nombre, frontmatter + contenido, cliente_id)
    print(f"✅ Fuente enviada: {nombre}")


async def guardar_literatura(contenido_llm: str, nombre: str, fuente: str, cliente_id: str):
    footer = f"\n\n---\n📄 Fuente: [[Fuentes/{fuente}]]\n"
    await _enviar_nota("literatura", f"{nombre}_lit", contenido_llm + footer, cliente_id)
    print(f"✅ Literatura enviada: {nombre}")


async def guardar_atomica(contenido_llm: str, nombre: str, fuente: str, cliente_id: str):
    nombre_archivo = nombre.replace("/", "-").replace(":", "").strip()
    footer = f"\n\n---\n📄 Extraído de: [[Literatura/{fuente}_lit]]\n"
    await _enviar_nota("atomica", nombre_archivo, contenido_llm + footer, cliente_id)
    _actualizar_indice(nombre, contenido_llm)
    print(f"✅ Atómica enviada: {nombre}")


async def guardar_moc(contenido_llm: str, materia: str, fuente: str, cliente_id: str):
    nombre_archivo = materia.replace("/", "-").replace(":", "").strip()
    footer = f"\n\n---\n📄 Última actualización desde: [[Literatura/{fuente}_lit]]\n"
    await _enviar_nota("moc", f"MOC_{nombre_archivo}", contenido_llm + footer, cliente_id)
    print(f"✅ MOC enviado: {materia}")

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