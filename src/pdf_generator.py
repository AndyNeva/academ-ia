"""
Genera un PDF con las notas Zettelkasten para enviarlo por Telegram.
Usado cuando el usuario elige destino PDF en lugar de Obsidian.
"""

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, PageBreak
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
    }
    return estilos


# ── Parser de Markdown simple ──────────────────────────────────

def _md_to_flowables(texto: str, estilos: dict) -> list:
    """Convierte Markdown básico a elementos de ReportLab."""
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

        # Headings
        if linea.startswith("# "):
            texto_h = linea[2:].strip()
            flowables.append(Paragraph(texto_h, estilos["h1"]))

        elif linea.startswith("## "):
            texto_h = linea[3:].strip()
            flowables.append(Paragraph(texto_h, estilos["h2"]))

        elif linea.startswith("### "):
            texto_h = linea[4:].strip()
            p = ParagraphStyle(
                "h3_inline",
                parent=estilos["body"],
                fontSize=11,
                textColor=colors.HexColor("#4a4a8a"),
                fontName="Helvetica-Bold",
            )
            flowables.append(Paragraph(texto_h, p))

        # Bullets
        elif linea.startswith("- "):
            texto_b = linea[2:].strip()
            # Limpiar backlinks [[X]] → X
            texto_b = texto_b.replace("[[", "").replace("]]", "")
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
            # Limpiar markdown inline básico
            texto_p = linea.strip()
            texto_p = texto_p.replace("**", "<b>", 1).replace("**", "</b>", 1)
            texto_p = texto_p.replace("[[", "").replace("]]", "")
            try:
                flowables.append(Paragraph(texto_p, estilos["body"]))
            except Exception:
                flowables.append(Paragraph(linea.strip(), estilos["body"]))

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
