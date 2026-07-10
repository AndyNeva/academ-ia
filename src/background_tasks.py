"""
Gestor de tareas en background para procesamiento de documentos.
Procesa PDFs asincronamente y notifica al cliente por WebSocket.
"""

import asyncio
import traceback
from typing import Callable, Optional
from datetime import datetime

# Almacenar tareas activas
active_tasks: dict[str, dict] = {}


async def run_background_task(
    task_id: str,
    cliente_id: str,
    task_func: Callable,
    on_success: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
    ws_manager=None
):
    """
    Ejecuta una tarea asincronamente y notifica el resultado por WebSocket.
    
    Args:
        task_id: ID único de la tarea
        cliente_id: ID del cliente (usuario)
        task_func: Función async a ejecutar
        on_success: Callback cuando termina bien
        on_error: Callback cuando hay error
        ws_manager: WebSocket manager para enviar notificaciones
    """
    try:
        # Registrar tarea activa
        active_tasks[task_id] = {
            "status": "processing",
            "cliente_id": cliente_id,
            "start_time": datetime.now(),
            "error": None
        }
        
        # Notificar que empezó
        if ws_manager and ws_manager.esta_conectado(cliente_id):
            await ws_manager.enviar(cliente_id, {
                "type": "task_started",
                "task_id": task_id,
                "mensaje": "Iniciando procesamiento del documento..."
            })
        
        # Ejecutar tarea
        result = await task_func()
        
        # Marcar como completada
        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result"] = result
        
        # Callback de éxito
        if on_success:
            await on_success(task_id, result)
        
        # Notificar éxito
        if ws_manager and ws_manager.esta_conectado(cliente_id):
            await ws_manager.enviar(cliente_id, {
                "type": "task_completed",
                "task_id": task_id,
                "status": "success",
                "mensaje": "✅ Documento procesado correctamente"
            })
        
        print(f"✅ Tarea {task_id} completada exitosamente\")\n        \n    except Exception as e:\n        error_msg = str(e)\n        error_type = type(e).__name__\n        \n        # Registrar error\n        active_tasks[task_id][\"status\"] = \"failed\"\n        active_tasks[task_id][\"error\"] = {\n            \"type\": error_type,\n            \"message\": error_msg,\n            \"traceback\": traceback.format_exc()\n        }\n        \n        print(f\"❌ Tarea {task_id} falló: {error_type}: {error_msg}\")\n        print(traceback.format_exc())\n        \n        # Callback de error\n        if on_error:\n            await on_error(task_id, e)\n        \n        # Notificar error específico por WebSocket\n        if ws_manager and ws_manager.esta_conectado(cliente_id):\n            # Mensajes específicos según el tipo de error\n            if \"OpenRouter\" in error_type or \"openai\" in error_msg.lower():\n                user_msg = \"❌ Error en el modelo de IA. Intenta de nuevo o contacta soporte.\"\n            elif \"timeout\" in error_msg.lower() or \"TimeoutError\" in error_type:\n                user_msg = \"⏱️ Timeout: el procesamiento tardó demasiado. Intenta con un documento más pequeño.\"\n            elif \"MinerU\" in error_msg or \"batch_id\" in error_msg.lower():\n                user_msg = \"❌ Error extrayendo el PDF. Asegúrate que sea un PDF válido.\"\n            elif \"database\" in error_msg.lower() or \"postgres\" in error_msg.lower():\n                user_msg = \"❌ Error guardando en la base de datos. Intenta de nuevo más tarde.\"\n            else:\n                user_msg = f\"❌ Error: {error_msg}\"\n            \n            await ws_manager.enviar(cliente_id, {\n                \"type\": \"task_failed\",\n                \"task_id\": task_id,\n                \"status\": \"error\",\n                \"error_type\": error_type,\n                \"user_message\": user_msg,\n                \"technical_message\": error_msg\n            })\n\n\ndef get_task_status(task_id: str) -> dict:\n    \"\"\"Obtiene el estado de una tarea.\"\"\"\n    return active_tasks.get(task_id, {\"status\": \"not_found\"})\n\n\ndef cleanup_task(task_id: str):\n    \"\"\"Limpia una tarea completada del registro.\"\"\"\n    if task_id in active_tasks:\n        del active_tasks[task_id]\n"
