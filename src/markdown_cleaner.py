import re

def limpiar_markdown(contenido: str) -> str:
    """
    Limpia el markdown generado por MinerU:
    - Elimina referencias a imágenes
    - Elimina líneas vacías múltiples
    - Elimina encabezados/pies de página repetidos
    """
    # Eliminar referencias a imágenes
    contenido = re.sub(r'!\[.*?\]\(.*?\)', '', contenido)
    
    # Eliminar líneas que solo tienen espacios
    contenido = re.sub(r'^\s+$', '', contenido, flags=re.MULTILINE)
    
    # Reducir múltiples líneas vacías a máximo 2
    contenido = re.sub(r'\n{3,}', '\n\n', contenido)
    
    return contenido.strip()
