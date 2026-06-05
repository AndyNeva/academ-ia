# AcademIA API - Guía de Uso

## 🚀 Instalación

### 1. Instalar dependencias de FastAPI

```bash
pip install fastapi uvicorn python-multipart
```

### 2. Configurar token de API

Edita `.env`:
```
API_TOKEN=tu_token_secreto_aqui
DEBUG=False
PORT=8000
```

---

## 🔄 Ejecutar la API

```bash
python api.py
```

La API estará disponible en: `http://localhost:8000`

### Documentación interactiva:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 📡 Endpoints Disponibles

### 1️⃣ Health Check
```http
GET /health
```

**Respuesta:**
```json
{
  "status": "ok",
  "timestamp": "2024-06-04T10:30:45.123456"
}
```

---

### 2️⃣ Procesar PDF completo
```http
POST /process_pdf?token=tu_token
Content-Type: multipart/form-data

file: [archivo.pdf]
```

**Qué hace:**
- ✅ Extrae texto con MinerU
- ✅ Guarda fuente cruda en Obsidian
- ✅ Genera nota de literatura con IA
- ✅ Genera notas atómicas
- ✅ Genera MOCs

**Respuesta exitosa:**
```json
{
  "status": "success",
  "nombre": "nombre_pdf",
  "mensaje": "PDF procesado correctamente",
  "resultado": {
    "notas_creadas": ["literatura", "atomicas", "mocs"]
  }
}
```

**Error (token inválido):**
```json
{
  "detail": "Token inválido"
}
```

---

### 3️⃣ Guardar nota manual
```http
POST /save_note?token=tu_token&tipo=literatura&nombre=Mi_Nota&contenido=# Contenido&materia=Opcional
```

**Parámetros:**
- `token` (requerido): Token de autenticación
- `tipo` (requerido): `literatura`, `atomica` o `moc`
- `nombre` (requerido): Nombre de la nota
- `contenido` (requerido): Contenido en Markdown
- `materia` (opcional): Categoría/asignatura

**Respuesta:**
```json
{
  "status": "success",
  "tipo": "literatura",
  "nombre": "Mi_Nota",
  "mensaje": "Nota guardada correctamente"
}
```

---

### 4️⃣ WebSocket (Obsidian Plugin)
```
ws://localhost:8000/ws
```

#### Paso 1: Autenticación
```json
{
  "type": "auth",
  "token": "tu_token_secreto"
}
```

**Respuesta (éxito):**
```json
{
  "type": "auth",
  "success": true,
  "mensaje": "Autenticación exitosa"
}
```

#### Paso 2: Enviar notas
```json
{
  "tipo": "literatura",
  "nombre": "Título de la nota",
  "contenido": "# Contenido en Markdown",
  "materia": "Tema opcional"
}
```

**Respuesta (éxito):**
```json
{
  "ok": true,
  "nombre": "Título de la nota",
  "tipo": "literatura",
  "mensaje": "Nota guardada exitosamente"
}
```

**Respuesta (error):**
```json
{
  "ok": false,
  "error": "Descripción del error"
}
```

---

## 🧪 Ejemplos de Uso

### Con cURL (Procesar PDF)
```bash
curl -X POST "http://localhost:8000/process_pdf?token=token_secreto_academia_ia_2024" \
  -F "file=@documento.pdf"
```

### Con Python (WebSocket)
```python
import asyncio
import json
import websockets

async def connect():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        # Autenticar
        await websocket.send(json.dumps({
            "type": "auth",
            "token": "token_secreto_academia_ia_2024"
        }))
        
        response = await websocket.recv()
        print(f"Auth: {response}")
        
        # Enviar nota
        await websocket.send(json.dumps({
            "tipo": "atomica",
            "nombre": "Concepto_Importante",
            "contenido": "# Definición\n\nEsta es una nota atómica importante.",
            "materia": "Biología"
        }))
        
        response = await websocket.recv()
        print(f"Guardada: {response}")

asyncio.run(connect())
```

### Con JavaScript (Obsidian Plugin)
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  // Autenticar
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'token_secreto_academia_ia_2024'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'auth' && data.success) {
    console.log('✅ Autenticado');
    
    // Enviar nota
    ws.send(JSON.stringify({
      tipo: 'literatura',
      nombre: 'Nuevo_Documento',
      contenido: '# Mi Documento\n\nContenido importante',
      materia: 'General'
    }));
  }
};
```

---

## 🔒 Seguridad

⚠️ **IMPORTANTE:**
- Cambia `API_TOKEN` en `.env` en producción
- Usa `wss://` (WebSocket Secure) en producción
- Implementa HTTPS en producción
- No compartas el token en URLs públicas

---

## 📊 Flujo completo

```
┌─────────────────┐
│   Cliente       │ (Obsidian, n8n, etc)
└────────┬────────┘
         │
         │ WebSocket con Token
         │
         ▼
┌─────────────────────────┐
│   API (FastAPI)         │
│ ├─ Valida token         │
│ ├─ Recibe notas/PDFs    │
│ └─ Procesa con scripts  │
└────────┬────────────────┘
         │
         │ Usa scripts internos
         │
         ▼
┌──────────────────────────────┐
│  Scripts (ai_processor,      │
│   pdf_extracter,             │
│   obsidian_exporter)         │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│  Obsidian Vault              │
│  ├─ Literatura/              │
│  ├─ Atomicas/               │
│  ├─ MOCs/                   │
│  └─ Fuentes/                │
└──────────────────────────────┘
```

---

## 🐛 Debugging

Activa modo debug en `.env`:
```
DEBUG=True
```

Luego ejecuta:
```bash
python api.py
```

Verás logs detallados de cada operación.

---

## 🤝 Integración con n8n

En tu workflow de n8n:
1. Usa `HTTP Request` node
2. URL: `http://tu-api:8000/process_pdf?token=tu_token`
3. Método: `POST`
4. Body: `form-data` con el PDF
5. Recibe respuesta JSON

---

¡Tu API está lista! 🎉
