import re

def limpiar_markdown(contenido: str) -> str:
    """
    Limpia el markdown generado por MinerU:
    - Elimina referencias a imágenes
    - Elimina líneas vacías múltiples
    - Elimina encabezados/pies de página repetidos
    - Repara fórmulas LaTeX que se rompen dentro de tablas Markdown
    """
    # Eliminar referencias a imágenes
    contenido = re.sub(r'!\[.*?\]\(.*?\)', '', contenido)

    # Eliminar líneas que solo tienen espacios
    contenido = re.sub(r'^\s+$', '', contenido, flags=re.MULTILINE)

    # Reducir múltiples líneas vacías a máximo 2
    contenido = re.sub(r'\n{3,}', '\n\n', contenido)

    # Reparar fórmulas dentro de tablas (antes de recortar espacios finales)
    contenido = _reparar_formulas_en_tablas(contenido)

    return contenido.strip()


# ── Reparación de fórmulas dentro de tablas ─────────────────────

def _reparar_formulas_en_tablas(contenido: str) -> str:
    """
    Las tablas Markdown usan '|' como separador de columnas. Cuando una celda
    contiene una fórmula LaTeX con '|' dentro (ej. valor absoluto, matrices),
    MinerU rompe la tabla porque interpreta ese '|' como un separador más.

    Esta función recorre solo las líneas que parecen filas de tabla
    (empiezan con '|') y, dentro de cada fórmula delimitada por $...$,
    escapa los '|' para que no rompan la estructura de la tabla.
    """
    lineas = contenido.split('\n')
    resultado = []

    for linea in lineas:
        if linea.strip().startswith('|') and '$' in linea:
            linea = _escapar_pipes_en_formulas(linea)
            linea = _normalizar_espacios_formula(linea)
        resultado.append(linea)

    return '\n'.join(resultado)


def _escapar_pipes_en_formulas(linea: str) -> str:
    """Escapa los '|' que aparezcan dentro de fórmulas inline $...$."""
    def reemplazar(match):
        formula = match.group(0)
        return formula.replace('|', r'\|')

    # Fórmulas inline: $ ... $ sin cruzar líneas
    return re.sub(r'\$[^\$\n]+\$', reemplazar, linea)


def _normalizar_espacios_formula(linea: str) -> str:
    """
    Corrige un problema común de MinerU: fórmulas que quedan pegadas al
    texto de la celda sin espacio (ej. 'Estereorradián$sr$') lo que a veces
    provoca que el renderer no las reconozca como bloque matemático.
    """
    # Asegura un espacio antes y después del '$' cuando está pegado a texto
    linea = re.sub(r'([^\s|$])\$', r'\1 $', linea)
    linea = re.sub(r'\$([^\s|$])', r'$ \1', linea)
    return linea