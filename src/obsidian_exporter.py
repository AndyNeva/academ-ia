from pathlib import Path
import json
import re
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# Referencia al WebSocket manager (se inyecta desde api.py)
_ws_manager = None

def set_ws_manager(manager):
    """api.py llama esto al iniciar para inyectar el manager de WebSockets."""
    global _ws_manager
    _ws_manager = manager


# ── Conexión PostgreSQL ────────────────────────────────────────

def _get_conn():
    """Retorna una conexión a PostgreSQL."""
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def init_db():
    """
    Crea la tabla atomicas si no existe.
    Llamar una vez al iniciar la API.
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS atomicas (
                cliente_id TEXT,
                nombre     TEXT,
                aliases    TEXT[],
                activa     BOOLEAN DEFAULT TRUE,
                PRIMARY KEY (cliente_id, nombre)
            )
        """)
        conn.commit()
        print("✅ Tabla atomicas lista")
    finally:
        conn.close()


# ── Índice multi-usuario con PostgreSQL ───────────────────────

def get_notas_existentes(cliente_id: str) -> list[dict]:
    """Retorna los conceptos activos del usuario."""
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT nombre, aliases
            FROM atomicas
            WHERE cliente_id = %s AND activa = TRUE
        """, (cliente_id,))
        rows = cur.fetchall()
        return [{"nombre": r["nombre"], "aliases": r["aliases"] or []} for r in rows]
    finally:
        conn.close()


def _actualizar_indice(nombre: str, contenido: str, cliente_id: str) -> None:
    """Inserta o reactiva un concepto en el índice del usuario."""
    aliases = _extraer_aliases(contenido)
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO atomicas (cliente_id, nombre, aliases, activa)
            VALUES (%s, %s, %s, TRUE)
            ON CONFLICT (cliente_id, nombre)
            DO UPDATE SET activa = TRUE, aliases = EXCLUDED.aliases
        """, (cliente_id, nombre, aliases))
        conn.commit()
    finally:
        conn.close()


def eliminar_del_indice(nombre: str, cliente_id: str) -> None:
    """Marca un concepto como inactivo cuando el usuario borra la nota."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE atomicas SET activa = FALSE
            WHERE cliente_id = %s AND nombre = %s
        """, (cliente_id, nombre))
        conn.commit()
        print(f"🗑️ Concepto marcado inactivo: {nombre} (usuario: {cliente_id})")
    finally:
        conn.close()


# ── WebSocket ──────────────────────────────────────────────────

async def _enviar_nota(tipo: str, nombre: str, contenido: str, cliente_id: str):
    """Envía la nota al plugin de Obsidian por WebSocket."""
    if _ws_manager is None:
        raise RuntimeError("WebSocket manager no configurado")
    await _ws_manager.enviar(cliente_id, {
        "tipo": tipo,
        "nombre": nombre,
        "contenido": contenido
    })


# ── Funciones públicas ─────────────────────────────────────────

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
    _actualizar_indice(nombre, contenido_llm, cliente_id)
    print(f"✅ Atómica enviada: {nombre}")


async def guardar_moc(contenido_llm: str, materia: str, fuente: str, cliente_id: str):
    nombre_archivo = materia.replace("/", "-").replace(":", "").strip()
    footer = f"\n\n---\n📄 Última actualización desde: [[Literatura/{fuente}_lit]]\n"
    await _enviar_nota("moc", f"MOC_{nombre_archivo}", contenido_llm + footer, cliente_id)
    print(f"✅ MOC enviado: {materia}")


# ── Helpers ────────────────────────────────────────────────────

def _extraer_aliases(contenido: str) -> list[str]:
    """Parsea el frontmatter YAML para extraer aliases."""
    match = re.search(r"aliases:\s*\[([^\]]*)\]", contenido)
    if not match:
        return []
    raw = match.group(1)
    return [a.strip().strip('"').strip("'") for a in raw.split(",") if a.strip()]