"""
Genera un PDF con las notas Zettelkasten para enviarlo por Telegram.
Usado cuando el usuario elige destino PDF en lugar de Obsidian.
"""

import io
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, PageBreak, Table, TableStyle
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER


# ── Estilos ────────────────────────────────────────────────────

def _get_styles():
    base = getSampleStyleSheet()

    estilos = {
        "titulo_doc": ParagraphStyle(
            "titulo_doc",
            parent=base["Title"],
            fontSize=20,
            textColor=colors.HexColor("#1a1a2e"),
            spaceAfter=6,
            alignment=TA_CENTER,
        ),
        "subtitulo": ParagraphStyle(
            "subtitulo",
            parent=base["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#4a4a8a"),
            spaceAfter=20,
            alignment=TA_CENTER,
        ),
        "tipo_badge": ParagraphStyle(
            "tipo_badge",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#7a7a9a"),
            spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontSize=16,
            textColor=colors.HexColor("#1a1a2e"),
            spaceBefore=12,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#2d2d5a"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#333333"),
            leading=15,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#333333"),
            leading=15,
            leftIndent=16,
            spaceAfter=3,
        ),
        "celda_tabla": ParagraphStyle(
            "celda_tabla",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#333333"),
            leading=12,
        ),
        "celda_header": ParagraphStyle(
            "celda_header",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#1a1a2e"),
            leading=12,
            fontName="Helvetica-Bold",
        ),
    }
    return estilos


# ── Conversión de texto inline (negrita + fórmulas + backlinks) ────

# Símbolos LaTeX comunes -> caracter Unicode equivalente.
# Se aplican ANTES de procesar ^ y _ porque algunos símbolos (\sum, \int)
# pueden ir seguidos de límites con esos operadores.
_SIMBOLOS_LATEX = {
    r"\times": "×", r"\cdot": "·", r"\pm": "±", r"\mp": "∓",
    r"\leq": "≤", r"\geq": "≥", r"\neq": "≠", r"\approx": "≈",
    r"\infty": "∞", r"\sum": "∑", r"\int": "∫", r"\sqrt": "√",
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\theta": "θ", r"\lambda": "λ", r"\mu": "μ", r"\pi": "π",
    r"\sigma": "σ", r"\omega": "ω", r"\Delta": "Δ", r"\Omega": "Ω",
    r"\rightarrow": "→", r"\Rightarrow": "⇒", r"\degree": "°",
}


def _formula_a_reportlab(formula: str) -> str:
    """
    Convierte una fórmula LaTeX simple (el contenido entre $...$) a
    marcado que ReportLab sí sabe renderizar (<super>, <sub>), en vez de
    dejar los símbolos LaTeX crudos como texto plano.
    """
    # Fracciones simples: \frac{a}{b} -> (a)/(b)
    formula = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', r'(\1)/(\2)', formula)

    # Símbolos comunes
    for latex, simbolo in _SIMBOLOS_LATEX.items():
        formula = formula.replace(latex, simbolo)

    # Superíndices: ^{...} o ^X (un solo caracter/dígito)
    formula = re.sub(r'\^\{([^{}]*)\}', r'<super>\1</super>', formula)
    formula = re.sub(r'\^(\w)', r'<super>\1</super>', formula)

    # Subíndices: _{...} o _X (un solo caracter/dígito)
    formula = re.sub(r'_\{([^{}]*)\}', r'<sub>\1</sub>', formula)
    formula = re.sub(r'_(\w)', r'<sub>\1</sub>', formula)

    return formula


def _procesar_texto_inline(texto: str) -> str:
    """
    Convierte un fragmento de texto (con posible Markdown y LaTeX) al
    marcado XML-like que ReportLab espera, de forma segura:
      1. Escapa caracteres especiales de XML (&, <, >) del texto ORIGINAL
         antes de insertar nuestras propias etiquetas, para que ReportLab
         nunca reciba tags mal formados.
      2. Convierte fórmulas $...$ a superíndices/subíndices reales.
      3. Convierte **negrita** (soporta varios pares en la misma línea).
      4. Limpia backlinks [[Concepto]] dejando solo el texto.
    """
    texto = texto.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    texto = re.sub(r'\$([^\$]+)\$', lambda m: _formula_a_reportlab(m.group(1)), texto)

    texto = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', texto)

    texto = texto.replace('[[', '').replace(']]', '')

    return texto


# ── Tablas ───────────────────────────────────────────────────────

_FILA_SEPARADORA = re.compile(r'^:?-{1,}:?$')


def _es_fila_separadora(celdas: list[str]) -> bool:
    """Detecta la fila |---|---|---| que separa encabezado del resto."""
    return all(_FILA_SEPARADORA.match(c.strip()) for c in celdas if c.strip() != "") and \
        any(c.strip() for c in celdas)


def _parsear_fila_tabla(linea: str) -> list[str]:
    fila = linea.strip()
    if fila.startswith('|'):
        fila = fila[1:]
    if fila.endswith('|'):
        fila = fila[:-1]
    return [c.strip() for c in fila.split('|')]


def _construir_tabla(filas_md: list[str], estilos: dict):
    """Convierte un bloque de filas Markdown '| a | b |' en un flowable
    Table real de ReportLab, con la primera fila como encabezado."""
    filas_celdas = [_parsear_fila_tabla(f) for f in filas_md]
    filas_celdas = [f for f in filas_celdas if not _es_fila_separadora(f)]

    if not filas_celdas:
        return None

    filas_flowable = []
    for idx, fila in enumerate(filas_celdas):
        estilo_celda = estilos["celda_header"] if idx == 0 else estilos["celda_tabla"]
        filas_flowable.append([
            Paragraph(_procesar_texto_inline(celda), estilo_celda)
            for celda in fila
        ])

    tabla = Table(filas_flowable, hAlign="LEFT")
    tabla.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8f5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabla


# ── Parser de Markdown ─────────────────────────────────────────

def _md_to_flowables(texto: str, estilos: dict) -> list:
    """Convierte Markdown básico (con tablas y fórmulas LaTeX simples) a
    elementos de ReportLab."""
    flowables = []
    lineas = texto.split("\n")
    i = 0

    while i < len(lineas):
        linea = lineas[i].rstrip()

        # Saltar frontmatter YAML
        if linea == "---" and i == 0:
            i += 1
            while i < len(lineas) and lineas[i].rstrip() != "---":
                i += 1
            i += 1
            continue

        # Tabla Markdown: recolectar todas las filas consecutivas
        if linea.strip().startswith('|'):
            filas_md = []
            while i < len(lineas) and lineas[i].strip().startswith('|'):
                filas_md.append(lineas[i])
                i += 1
            tabla = _construir_tabla(filas_md, estilos)
            if tabla:
                flowables.append(Spacer(1, 6))
                flowables.append(tabla)
                flowables.append(Spacer(1, 6))
            continue

        # Headings
        if linea.startswith("# "):
            flowables.append(Paragraph(_procesar_texto_inline(linea[2:].strip()), estilos["h1"]))

        elif linea.startswith("## "):
            flowables.append(Paragraph(_procesar_texto_inline(linea[3:].strip()), estilos["h2"]))

        elif linea.startswith("### "):
            p = ParagraphStyle(
                "h3_inline",
                parent=estilos["body"],
                fontSize=11,
                textColor=colors.HexColor("#4a4a8a"),
                fontName="Helvetica-Bold",
            )
            flowables.append(Paragraph(_procesar_texto_inline(linea[4:].strip()), p))

        # Bullets
        elif linea.startswith("- "):
            texto_b = _procesar_texto_inline(linea[2:].strip())
            flowables.append(Paragraph(f"• {texto_b}", estilos["bullet"]))

        # Línea horizontal
        elif linea.startswith("---"):
            flowables.append(Spacer(1, 4))
            flowables.append(HRFlowable(
                width="100%", thickness=0.5,
                color=colors.HexColor("#cccccc")
            ))
            flowables.append(Spacer(1, 4))

        # Texto normal (ignorar líneas vacías múltiples)
        elif linea.strip():
            try:
                flowables.append(Paragraph(_procesar_texto_inline(linea.strip()), estilos["body"]))
            except Exception:
                # Último recurso: texto plano sin ningún marcado, para no tumbar el PDF
                texto_plano = re.sub(r'[<>&]', '', linea.strip())
                flowables.append(Paragraph(texto_plano, estilos["body"]))

        else:
            flowables.append(Spacer(1, 6))

        i += 1

    return flowables


# ── Generador principal ────────────────────────────────────────

def generar_pdf(
    filename: str,
    literatura: str,
    atomicas: list[str],
    moc: str
) -> bytes:
    """
    Genera un PDF con todas las notas y devuelve los bytes.

    Args:
        filename:   Nombre del documento fuente
        literatura: Contenido de la nota de literatura
        atomicas:   Lista de contenidos de notas atómicas
        moc:        Contenido del MOC

    Returns:
        bytes del PDF generado
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    estilos = _get_styles()
    story = []

    # ── Portada ──────────────────────────────────────────
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph("📚 AcademIA", estilos["titulo_doc"]))
    story.append(Paragraph(f"Notas de: {filename}", estilos["subtitulo"]))
    story.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#4a4a8a")
    ))
    story.append(Spacer(1, 1 * cm))

    # Resumen de contenido
    story.append(Paragraph(
        f"Este documento contiene <b>{len(atomicas)} notas atómicas</b>, "
        f"una nota de literatura y un mapa de contenido (MOC).",
        estilos["body"]
    ))
    story.append(PageBreak())

    # ── Nota de Literatura ───────────────────────────────
    story.append(Paragraph("📄 NOTA DE LITERATURA", estilos["tipo_badge"]))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#4a4a8a")
    ))
    story.append(Spacer(1, 6))
    story += _md_to_flowables(literatura, estilos)
    story.append(PageBreak())

    # ── Notas Atómicas ───────────────────────────────────
    story.append(Paragraph("⚛️ NOTAS ATÓMICAS", estilos["tipo_badge"]))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#4a4a8a")
    ))
    story.append(Spacer(1, 6))

    for i, atomica in enumerate(atomicas):
        story += _md_to_flowables(atomica, estilos)
        if i < len(atomicas) - 1:
            story.append(Spacer(1, 8))
            story.append(HRFlowable(
                width="60%", thickness=0.3,
                color=colors.HexColor("#dddddd")
            ))
            story.append(Spacer(1, 8))

    story.append(PageBreak())

    # ── MOC ──────────────────────────────────────────────
    story.append(Paragraph("🗺️ MAPA DE CONTENIDO (MOC)", estilos["tipo_badge"]))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#4a4a8a")
    ))
    story.append(Spacer(1, 6))
    story += _md_to_flowables(moc, estilos)

    doc.build(story)
    return buffer.getvalue()