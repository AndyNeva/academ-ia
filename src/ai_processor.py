import os
import re
import json
from datetime import date
from openai import OpenAI
from dotenv import load_dotenv
from src.obsidian_exporter import guardar_literatura, guardar_atomica, guardar_moc, get_notas_existentes

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Modelo usado para generar las notas.
# NOTA: si MODEL es un modelo de razonamiento (o3, o4-mini, o1, etc.),
# la Chat Completions API exige `max_completion_tokens` en vez de `max_tokens`
# (ya aplicado en _call_ai más abajo).
MODEL = "o4-mini"

# ─────────────────────────────────────────
# SYSTEM PROMPTS
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

## Observaciones
Espacio para contexto adicional: por qué es relevante, limitaciones, etc.

REGLAS:
- No inventes contenido que no esté en el texto
- Los backlinks deben ser conceptos reales mencionados en el documento
- Los tags NUNCA deben tener espacios: usa una sola palabra o varias unidas con guiones
  (ej. "sistemas-de-unidades", nunca "sistemas de unidades")
- Responde ÚNICAMENTE con el Markdown, sin explicaciones adicionales, sin envolver
  la respuesta en bloques de código (nada de ```markdown ni ``` al inicio o final)
"""

PROMPT_ATOMICA = """
Eres un experto en organización de conocimiento académico (método Zettelkasten).
Tu tarea es generar NOTAS ATÓMICAS a partir del texto extraído de un documento académico.

Una nota atómica = UN solo concepto, explicado con precisión y en profundidad. Si el texto
contiene N conceptos importantes, genera N notas separadas. Devuelve todas en un solo bloque,
separadas por: ===NOTA===

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
Explicación amplia y detallada: contexto, matices, fórmulas si aplica, cómo se relaciona
con otros conceptos del mismo documento. Escribe con profundidad, no te limites a una
o dos oraciones — el objetivo es que la nota sea autosuficiente para entender el concepto
sin volver al documento original.

## Ejemplo de aplicación
Un caso concreto (numérico, práctico o de la vida real según el tema) que muestre cómo
se usa o se manifiesta este concepto. Si el concepto tiene una fórmula, resuélvela con
números de ejemplo. Si es un concepto teórico, da un caso de uso real.

## Relacionado con
- [[Concepto relacionado 1]]
- [[Concepto relacionado 2]]

## Aparece en
- [[Nota de literatura de origen]]

REGLAS:
- Máximo un concepto por nota
- Usa [[backlinks]] para conectar conceptos entre sí
- Sé preciso: preserva términos técnicos, fórmulas y definiciones exactas
- Las notas deben ser más extensas que una definición de diccionario: incluye matices,
  contexto y el ejemplo de aplicación pedido arriba
- Los tags NUNCA deben tener espacios: usa una sola palabra o varias unidas con guiones
  (ej. "unidad-de-medida", nunca "unidad de medida")
- Responde ÚNICAMENTE con el Markdown separado por ===NOTA===, sin explicaciones
  adicionales, sin envolver la respuesta en bloques de código (nada de ```markdown ni ```)
"""

PROMPT_MOC = """
Eres un experto en organización de conocimiento académico (método Zettelkasten).
Tu tarea es generar o ACTUALIZAR un MOC (Map of Content) que organice, en forma de ruta
de aprendizaje, un conjunto de notas atómicas YA EXISTENTES en la base de conocimiento del usuario.

IMPORTANTE: No inventes conceptos nuevos. Usa EXCLUSIVAMENTE los nombres de notas atómicas
que se te proporcionan en la lista. No agregues ningún concepto que no esté en esa lista.

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

## Ruta de aprendizaje

### Conceptos fundamentales
- [[Concepto base 1]]
- [[Concepto base 2]]

### Conceptos avanzados
- [[Concepto avanzado 1]]

## Documentos fuente
- [[Nota de literatura 1]]

REGLAS:
- Usa ÚNICAMENTE los conceptos de la lista proporcionada, ninguno inventado
- Agrupa los conceptos por nivel de complejidad o dependencia lógica (qué debería aprenderse antes)
- Usa SOLO [[backlinks]] con los nombres EXACTOS que se te dieron, sin explicar el contenido de cada nota
- Los tags NUNCA deben tener espacios: usa una sola palabra o varias unidas con guiones
- Este archivo es un índice, no un resumen
- Responde ÚNICAMENTE con el Markdown, sin explicaciones adicionales, sin envolver la
  respuesta en bloques de código (nada de ```markdown ni ```)
"""

PROMPT_RESOLVER_DUPLICADOS = """
Eres un experto en gestión de conocimiento académico (Zettelkasten).

Se te dará:
1. Una lista de notas atómicas YA EXISTENTES (nombre + aliases)
2. Una lista de conceptos NUEVOS que se quieren crear

Tu tarea es decidir para cada concepto nuevo:
- NUEVO: no existe nada similar → se crea nota nueva
- FUSIONAR con [[Nota existente]]: es el mismo concepto con otro nombre → no se crea
- RELACIONAR con [[Nota existente]]: es un concepto distinto pero muy cercano → se crea con backlink

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
# Helper central con fallback de modelos
# ─────────────────────────────────────────

def _call_ai(system: str, user: str, max_tokens: int = 8096) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user}
        ],
        # Los modelos de razonamiento (o3 / o4-mini / o1) requieren
        # max_completion_tokens; con Chat Completions "max_tokens" ya no
        # es válido para ellos.
        max_completion_tokens=max_tokens
    )
    return response.choices[0].message.content


# ─────────────────────────────────────────
# Post-procesamiento de la respuesta de la IA
# ─────────────────────────────────────────
# Estas funciones corrigen por código lo que la IA puede olvidar u
# obedecer de forma inconsistente: bloques de código sobrantes, fechas
# y tags con espacios. No dependen de que el modelo "se acuerde".

def _limpiar_respuesta_ia(texto: str) -> str:
    """Quita fences ```markdown / ``` que el modelo a veces agrega
    aunque se le pida no hacerlo."""
    texto = texto.strip()
    texto = re.sub(r'^```(?:markdown|md)?\s*\n', '', texto)
    texto = re.sub(r'\n?```\s*$', '', texto)
    return texto.strip()


def _insertar_fecha_real(md: str) -> str:
    """Reemplaza cualquier valor en la línea 'created:' (incluyendo
    placeholders sin resolver como {{fecha_hoy}} o fechas inventadas)
    por la fecha real del sistema."""
    fecha_hoy = date.today().isoformat()

    if re.search(r'(?m)^created:.*$', md):
        return re.sub(r'(?m)^created:.*$', f'created: {fecha_hoy}', md)

    # Si no existe línea 'created:' pero sí hay frontmatter, la insertamos
    if md.lstrip().startswith('---'):
        return re.sub(r'^---\n', f'---\ncreated: {fecha_hoy}\n', md, count=1)

    return md


def _sanitizar_tags(md: str) -> str:
    """Reemplaza espacios dentro de cada tag por guiones, para que
    Obsidian no los muestre como tags inválidos/tachados."""
    def reemplazar(match):
        contenido = match.group(1)
        tags = [t.strip().strip('"').strip("'") for t in contenido.split(',') if t.strip()]
        tags_limpios = [re.sub(r'\s+', '-', t) for t in tags]
        return f"tags: [{', '.join(tags_limpios)}]"

    return re.sub(r'tags:\s*\[([^\]]*)\]', reemplazar, md)


def _post_procesar(md: str) -> str:
    """Pipeline de limpieza aplicado a toda nota generada por la IA."""
    md = _limpiar_respuesta_ia(md)
    md = _insertar_fecha_real(md)
    md = _sanitizar_tags(md)
    return md


# ─────────────────────────────────────────
# Generadores por tipo de nota
# ─────────────────────────────────────────

def generate_literatura(raw_text: str, filename: str = "") -> str:
    user_prompt = f"""Genera la nota de literatura para el documento: {filename}

--- TEXTO EXTRAÍDO ---
{raw_text}
--- FIN DEL TEXTO ---"""
    resultado = _call_ai(PROMPT_LITERATURA, user_prompt)
    return _post_procesar(resultado)


def generate_atomicas(raw_text: str, filename: str = "") -> list[str]:
    user_prompt = f"""Genera las notas atómicas para el documento: {filename}

--- TEXTO EXTRAÍDO ---
{raw_text}
--- FIN DEL TEXTO ---"""
    # max_tokens más alto: las notas ahora son más largas (Desarrollo + Ejemplo de aplicación)
    result = _call_ai(PROMPT_ATOMICA, user_prompt, max_tokens=12288)
    result = _limpiar_respuesta_ia(result)  # por si envuelve toda la respuesta en un solo bloque
    notas = [n.strip() for n in result.split("===NOTA===") if n.strip()]
    return [_post_procesar(n) for n in notas]


def generate_moc(conceptos: list[str], filename: str = "", materia: str = "") -> str:
    conceptos_txt = "\n".join(f"- {c}" for c in conceptos) if conceptos else "(sin notas atómicas disponibles)"
    user_prompt = f"""Genera el MOC para la materia: {materia or 'inferida del documento'}
Documento fuente: {filename}

--- NOTAS ATÓMICAS DISPONIBLES (usa solo estas, no inventes otras) ---
{conceptos_txt}
--- FIN DE LA LISTA ---"""
    resultado = _call_ai(PROMPT_MOC, user_prompt)
    return _post_procesar(resultado)


def resolver_duplicados(conceptos_nuevos: list[str], notas_existentes: list[dict]) -> list[dict]:
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

    raw = _call_ai(PROMPT_RESOLVER_DUPLICADOS, user_prompt, max_tokens=8192)
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(clean)

# ─────────────────────────────────────────
# Orquestador principal
# ─────────────────────────────────────────

async def process_document(
    raw_text: str,
    filename: str = "",
    materia: str = "",
    cliente_id: str = "",
    destino: str = "obsidian"  # "obsidian" | "pdf"
) -> dict:
    """
    Orquesta el procesamiento completo de un documento.

    Args:
        raw_text:   Texto extraído del documento
        filename:   Nombre del archivo fuente
        materia:    Materia opcional (la IA la infiere si no se da)
        cliente_id: ID de Telegram del usuario
        destino:    "obsidian" envía por WebSocket | "pdf" devuelve contenido

    Returns:
        dict con resultado. Si destino="pdf" incluye bytes del PDF en "pdf_bytes".
    """
    resultado = {
        "literatura": None,
        "atomicas": [],
        "fusiones": [],
        "moc": None,
        "pdf_bytes": None
    }

    # 1. Nota de literatura
    print(f"[1/4] Generando nota de literatura para: {filename}")
    lit = generate_literatura(raw_text, filename)
    resultado["literatura"] = lit

    if destino == "obsidian":
        await guardar_literatura(lit, filename, filename, cliente_id)

    # 2. Generar atómicas candidatas
    print(f"[2/4] Generando notas atómicas...")
    atomicas = generate_atomicas(raw_text, filename)
    conceptos_nuevos = [_extract_title(n) for n in atomicas]
    print(f"→ {len(atomicas)} candidatas generadas")

    # 3. Resolver duplicados
    print(f"[3/4] Resolviendo duplicados semánticos...")
    if destino == "obsidian":
        notas_existentes = get_notas_existentes(cliente_id)
    else:
        # destino == "pdf": el PDF no tiene un vault compartido donde el usuario
        # pueda encontrar notas atómicas creadas en el pasado, así que no hay
        # "duplicados" que resolver contra nada — todo se genera como si
        # ningún concepto existiera previamente.
        print("   (destino=pdf: se ignora la base de atómicas existentes, todo se trata como nuevo)")
        notas_existentes = []
    decisiones = resolver_duplicados(conceptos_nuevos, notas_existentes)
    notas_por_nombre = {_extract_title(n): n for n in atomicas}
    atomicas_guardadas = []

    for decision in decisiones:
        nombre = decision["concepto_nuevo"]
        accion = decision["accion"]
        nota_existente = decision.get("nota_existente")

        if accion == "NUEVO":
            print(f"      ✅ NUEVO: {nombre}")
            contenido = notas_por_nombre.get(nombre, "")
            if contenido:
                atomicas_guardadas.append(contenido)
                resultado["atomicas"].append(nombre)
                if destino == "obsidian":
                    await guardar_atomica(contenido, nombre, filename, cliente_id)

        elif accion == "FUSIONAR":
            print(f"      🔀 FUSIONAR: '{nombre}' → [[{nota_existente}]]")
            resultado["fusiones"].append({
                "concepto_descartado": nombre,
                "usar_en_su_lugar": nota_existente,
            })

        elif accion == "RELACIONAR":
            print(f"      🔗 RELACIONAR: '{nombre}' → backlink a [[{nota_existente}]]")
            contenido = notas_por_nombre.get(nombre, "")
            contenido = _inject_backlink(contenido, nota_existente)
            if contenido:
                atomicas_guardadas.append(contenido)
                resultado["atomicas"].append(nombre)
                if destino == "obsidian":
                    await guardar_atomica(contenido, nombre, filename, cliente_id)

    # 4. MOC — construido SOLO con notas atómicas reales (existentes + nuevas de este documento)
    print(f"[4/4] Generando MOC...")
    nombres_existentes = [n["nombre"] for n in notas_existentes]
    conceptos_para_moc = list(dict.fromkeys(nombres_existentes + resultado["atomicas"]))
    moc = generate_moc(conceptos_para_moc, filename, materia)
    resultado["moc"] = moc

    if destino == "obsidian":
        await guardar_moc(moc, filename, filename, cliente_id)

    # 5. Si destino es PDF, generar el archivo
    elif destino == "pdf":
        print("[5/5] Generando PDF...")
        from src.pdf_generator import generar_pdf
        pdf_bytes = generar_pdf(
            filename=filename,
            literatura=lit,
            atomicas=atomicas_guardadas,
            moc=moc
        )
        resultado["pdf_bytes"] = pdf_bytes
        print(f"✅ PDF generado: {len(pdf_bytes)} bytes")

    return resultado


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _inject_backlink(contenido: str, nota_relacionada: str) -> str:
    linea = f"- [[{nota_relacionada}]] ← concepto cercano"
    if "## Relacionado con" in contenido:
        return contenido.replace(
            "## Relacionado con",
            f"## Relacionado con\n{linea}"
        )
    return contenido + f"\n\n## Relacionado con\n{linea}"