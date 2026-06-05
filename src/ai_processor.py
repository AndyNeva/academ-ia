import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from src.obsidian_exporter import guardar_literatura, guardar_atomica, guardar_moc, get_notas_existentes

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

MODEL = "google/gemma-4-31b-it:free"

# ─────────────────────────────────────────
# SYSTEM PROMPTS por tipo de nota
# ─────────────────────────────────────────

PROMPT_LITERATURA = """
Eres un experto en organización de conocimiento académico (método Zettelkasten).
Tu tarea es generar una NOTA DE LITERATURA a partir del texto extraído de un documento académico.

Una nota de literatura representa el documento completo como fuente. Sigue esta estructura:

FRONTMATTER:
---
type: literatura
tags: [literatura, {{tema_principal}}]
aliases: []
created: {{fecha_hoy}}
source: PDF
---

CUERPO:
# {{Título del documento}}

## Metadatos
- **Autor**: (si se puede inferir)
- **Tipo**: libro / artículo / diapositivas
- **Materia**: (inferida del contenido)

## Resumen general
3-5 párrafos que describan de qué trata el documento, su propósito y contexto.

## Conceptos extraídos
Lista de los conceptos clave encontrados, como backlinks para Obsidian:
- [[Concepto 1]]
- [[Concepto 2]]

## Observaciones
Espacio para contexto adicional: por qué es relevante, limitaciones, etc.

REGLAS:
- No inventes contenido que no esté en el texto
- Los backlinks deben ser conceptos reales mencionados en el documento
- Responde ÚNICAMENTE con el Markdown, sin explicaciones adicionales
"""

PROMPT_ATOMICA = """
Eres un experto en organización de conocimiento académico (método Zettelkasten).
Tu tarea es generar NOTAS ATÓMICAS a partir del texto extraído de un documento académico.

Una nota atómica = UN solo concepto, explicado con precisión. Si el texto contiene N conceptos importantes,
genera N notas separadas. Devuelve todas en un solo bloque, separadas por: ===NOTA===

Cada nota atómica sigue esta estructura:

---
type: atomica
tags: [atomica, {{tema}}]
aliases: []
created: {{fecha_hoy}}
---

# {{Nombre del concepto}}

## Definición
Explicación clara y precisa del concepto en 2-4 oraciones.

## Desarrollo
Explicación más amplia, ejemplos, fórmulas si aplica.

## Relacionado con
- [[Concepto relacionado 1]]
- [[Concepto relacionado 2]]

## Aparece en
- [[Nota de literatura de origen]]

REGLAS:
- Máximo un concepto por nota
- Usa [[backlinks]] para conectar conceptos entre sí
- Sé preciso: preserva términos técnicos, fórmulas y definiciones exactas
- Responde ÚNICAMENTE con el Markdown separado por ===NOTA===, sin explicaciones adicionales
"""

PROMPT_MOC = """
Eres un experto en organización de conocimiento académico (método Zettelkasten).
Tu tarea es generar o ACTUALIZAR un MOC (Map of Content) a partir de los conceptos
extraídos de un documento académico.

Un MOC es una nota de navegación: no contiene conocimiento nuevo, solo organiza y conecta.

Sigue esta estructura:

---
type: moc
tags: [moc, {{materia}}]
created: {{fecha_hoy}}
---

# MOC — {{Nombre de la materia o tema general}}

## Descripción
Una o dos oraciones explicando de qué trata este mapa de conocimiento.

## Conceptos fundamentales
- [[Concepto base 1]]
- [[Concepto base 2]]

## Conceptos avanzados
- [[Concepto avanzado 1]]

## Documentos fuente
- [[Nota de literatura 1]]
- [[Nota de literatura 2]]

REGLAS:
- Agrupa los conceptos por nivel de complejidad o subtema
- Usa SOLO [[backlinks]], sin explicar el contenido de cada nota
- Este archivo es un índice, no un resumen
- Responde ÚNICAMENTE con el Markdown, sin explicaciones adicionales
"""

PROMPT_RESOLVER_DUPLICADOS = """
Eres un experto en gestión de conocimiento académico (Zettelkasten).

Se te dará:
1. Una lista de notas atómicas YA EXISTENTES (nombre + aliases)
2. Una lista de conceptos NUEVOS que se quieren crear

Tu tarea es decidir para cada concepto nuevo:
- NUEVO: no existe nada similar → se crea nota nueva
- FUSIONAR con [[Nota existente]]: es el mismo concepto con otro nombre → no se crea, se añade alias
- RELACIONAR con [[Nota existente]]: es un concepto distinto pero muy cercano → se crea nuevo con backlink

Responde ÚNICAMENTE en JSON con esta estructura:
[
  {
    "concepto_nuevo": "nombre del concepto nuevo",
    "accion": "NUEVO" | "FUSIONAR" | "RELACIONAR",
    "nota_existente": "nombre de la nota existente o null",
    "alias_sugerido": "nombre alternativo a añadir como alias o null"
  }
]
"""

# ─────────────────────────────────────────
# Helper central
# ─────────────────────────────────────────

def _call_ai(system: str, user: str, max_tokens: int = 8096) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user}
        ],
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

# ─────────────────────────────────────────
# Generadores por tipo de nota
# ─────────────────────────────────────────

def generate_literatura(raw_text: str, filename: str = "") -> str:
    user_prompt = f"""Genera la nota de literatura para el documento: {filename}

--- TEXTO EXTRAÍDO ---
{raw_text}
--- FIN DEL TEXTO ---"""
    return _call_ai(PROMPT_LITERATURA, user_prompt)


def generate_atomicas(raw_text: str, filename: str = "") -> list[str]:
    """Devuelve una lista de notas atómicas, una por concepto."""
    user_prompt = f"""Genera las notas atómicas para el documento: {filename}

--- TEXTO EXTRAÍDO ---
{raw_text}
--- FIN DEL TEXTO ---"""
    result = _call_ai(PROMPT_ATOMICA, user_prompt)
    # Separar en notas individuales
    notas = [n.strip() for n in result.split("===NOTA===") if n.strip()]
    return notas


def generate_moc(raw_text: str, filename: str = "", materia: str = "") -> str:
    user_prompt = f"""Genera el MOC para la materia: {materia or 'inferida del documento'}
Documento fuente: {filename}

--- TEXTO EXTRAÍDO ---
{raw_text}
--- FIN DEL TEXTO ---"""
    return _call_ai(PROMPT_MOC, user_prompt)

def resolver_duplicados(conceptos_nuevos: list[str], notas_existentes: list[dict]) -> list[dict]:
    """
    Decide si cada concepto nuevo es duplicado, alias o concepto distinto.
    
    Args:
        conceptos_nuevos:  títulos extraídos de las notas atómicas nuevas
        notas_existentes:  índice de notas ya guardadas en Obsidian
    
    Returns:
        lista de decisiones por concepto
    """
    if not notas_existentes:
        return [{"concepto_nuevo": c, "accion": "NUEVO", 
                 "nota_existente": None, "alias_sugerido": None}
                for c in conceptos_nuevos]

    existentes_txt = "\n".join(
        f"- {n['nombre']}" + (f" (aliases: {', '.join(n['aliases'])})" 
                               if n.get('aliases') else "")
        for n in notas_existentes
    )

    nuevos_txt = "\n".join(f"- {c}" for c in conceptos_nuevos)

    user_prompt = f"""NOTAS EXISTENTES:
{existentes_txt}

CONCEPTOS NUEVOS A EVALUAR:
{nuevos_txt}

Devuelve el JSON de decisiones."""

    raw = _call_ai(PROMPT_RESOLVER_DUPLICADOS, user_prompt, max_tokens=2048)
    
    # Limpiar posibles ```json ... ``` que el modelo añada
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(clean)

# ─────────────────────────────────────────
# Orquestador principal
# ─────────────────────────────────────────

def process_document(raw_text: str, filename: str = "", materia: str = "") -> dict:
    """
    Orquesta el procesamiento completo de un documento.
    Llama a las tres funciones de guardado que recibe como parámetro.

    Args:
        raw_text:        Texto extraído del PDF o MD completo
        filename:        Nombre del archivo fuente
        materia:         Materia o área temática (opcional, la IA la infiere)
        save_literatura: fn(content: str, filename: str) → str (ruta guardada)
        save_atomica:    fn(content: str, concept_name: str) → str
        save_moc:        fn(content: str, materia: str) → str

    Returns:
        dict con rutas de archivos creados
    """
    resultado = {
    "literatura": None,
    "atomicas": [],
    "fusiones": [],
    "moc": None
}

     # 1. Nota de literatura
    print(f"[1/4] Generando nota de literatura para: {filename}")
    lit = generate_literatura(raw_text, filename)
    if guardar_literatura:
        ruta = guardar_literatura(lit, filename, filename)
        resultado["literatura"] = ruta
    else:
        resultado["literatura"] = lit

    # 2. Generar atómicas candidatas
    print(f"[2/4] Generando notas atómicas...")
    atomicas = generate_atomicas(raw_text, filename)
    conceptos_nuevos = [_extract_title(n) for n in atomicas]
    print(f"→ {len(atomicas)} candidatas generadas")
    
    # 3. Resolver duplicados contra las existentes
    print(f"[3/4] Resolviendo duplicados semánticos...")
    notas_existentes = get_notas_existentes() if get_notas_existentes else []
    decisiones = resolver_duplicados(conceptos_nuevos, notas_existentes)

    # Mapear nombre → contenido completo de la nota generada
    notas_por_nombre = {_extract_title(n): n for n in atomicas}

    for decision in decisiones:
        nombre = decision["concepto_nuevo"]
        accion = decision["accion"]
        nota_existente = decision.get("nota_existente")

        if accion == "NUEVO":
            print(f"      ✅ NUEVO: {nombre}")
            contenido = notas_por_nombre.get(nombre, "")
            if guardar_atomica and contenido:
                ruta = guardar_atomica(contenido, nombre, filename)
                resultado["atomicas"].append(ruta)

        elif accion == "FUSIONAR":
            print(f"      🔀 FUSIONAR: '{nombre}' → alias de [[{nota_existente}]]")
            resultado["fusiones"].append({
            "concepto_descartado": nombre,
            "usar_en_su_lugar": nota_existente,
             })

        elif accion == "RELACIONAR":
            print(f"      🔗 RELACIONAR: '{nombre}' → backlink a [[{nota_existente}]]")
            contenido = notas_por_nombre.get(nombre, "")
            # Inyectar backlink adicional antes de guardar
            contenido = _inject_backlink(contenido, nota_existente)
            if guardar_atomica and contenido:
                ruta = guardar_atomica(contenido, nombre, filename)
                resultado["atomicas"].append(ruta)

    # 4. MOC
    print(f"[4/4] Generando MOC...")
    moc = generate_moc(raw_text, filename, materia)
    if guardar_moc:
        ruta = guardar_moc(moc, materia or filename, filename)
        resultado["moc"] = ruta
    else:
        resultado["moc"] = moc

    return resultado


def _extract_title(markdown: str) -> str:
    """Extrae el título # de una nota Markdown."""
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""

def _inject_backlink(contenido: str, nota_relacionada: str) -> str:
    """Añade un backlink extra en la sección Relacionado con."""
    linea = f"- [[{nota_relacionada}]] ← concepto cercano"
    if "## Relacionado con" in contenido:
        return contenido.replace(
            "## Relacionado con",
            f"## Relacionado con\n{linea}"
        )
    return contenido + f"\n\n## Relacionado con\n{linea}"


# ─────────────────────────────────────────
# Versión chunked para PDFs largos
# ─────────────────────────────────────────

def process_document_chunked(
    pages: list[str],
    filename: str = "",
    materia: str = "",
    save_literatura=None,
    save_atomica=None,
    save_moc=None,
    chunk_size: int = 10
) -> dict:
    """
    Para PDFs largos: procesa por chunks y luego orquesta
    las tres notas sobre el texto integrado.
    """
    chunks_md = []
    total = (len(pages) - 1) // chunk_size + 1

    for i in range(0, len(pages), chunk_size):
        chunk = pages[i:i + chunk_size]
        chunk_text = "\n\n".join(chunk)
        num = i // chunk_size + 1
        print(f"   → Chunk {num}/{total}...")

        result = _call_ai(
            "Extrae el contenido académico de esta sección en Markdown limpio y estructurado.",
            f"Parte {num}/{total} de {filename}:\n\n{chunk_text}",
            max_tokens=4096
        )
        chunks_md.append(result)

    print("   → Integrando chunks...")
    integrated = _call_ai(
        "Integra estas partes en un solo texto académico coherente en Markdown. Elimina duplicados.",
        "===SEPARADOR===".join(chunks_md),
        max_tokens=8096
    )

    return process_document(
        raw_text=integrated,
        filename=filename,
        materia=materia,
        save_literatura=save_literatura,
        save_atomica=save_atomica,
        save_moc=save_moc
    )