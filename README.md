# 🎓 AcademIA - API para Procesar PDFs y Gestionar Notas

API en FastAPI que procesa documentos PDF y genera notas estructuradas en Obsidian usando el método Zettelkasten. Integrable con n8n y Obsidian plugins.

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green?style=flat-square)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?style=flat-square)
![Railway](https://img.shields.io/badge/Railway-Deployment-purple?style=flat-square)

---

## 🚀 Features

- ✅ **Procesa PDFs** - Extrae contenido con MinerU + IA
- ✅ **Genera 3 tipos de notas:**
  - 📚 **Literatura:** Resumen completo del documento
  - 🔗 **Atómicas:** Un concepto = Una nota
  - 🗺️ **MOCs:** Índices temáticos (Map of Content)
- ✅ **WebSocket** - Comunicación en tiempo real con Obsidian
- ✅ **REST API** - Endpoints para procesar PDFs y guardar notas
- ✅ **Autenticación** - Token-based para seguridad
- ✅ **Docker Ready** - Deploy en Railway con 1 click
- ✅ **Deduplicación** - Evita crear notas duplicadas con IA

---

## 📋 Stack

- **Backend:** FastAPI + Uvicorn
- **PDF Processing:** MinerU + OpenRouter (IA)
- **Storage:** Obsidian Vault (local) + WebSocket (real-time)
- **Deployment:** Docker + Railway
- **Python:** 3.11+

---

## 🎯 Casos de Uso

1. **Estudiantes/Investigadores:** Procesa tus apuntes y crea base de conocimiento automáticamente
2. **n8n Workflows:** Integra con n8n para automatizar de principio a fin
3. **Obsidian Power Users:** Mantén tu bóveda sincronizada con IA

---

## ⚡ Quickstart

### Local

```bash
# 1. Instalar dependencias
python start_api.py --install

# 2. Iniciar API
python start_api.py

# 3. Ir a http://localhost:8000/docs
```

### Production (Railway)

```bash
# 1. Crear repo en GitHub
git init
git add .
git commit -m "Initial commit"
git push

# 2. En https://railway.app:
# - Conectar repo GitHub
# - Setear variables (API_TOKEN, OPENROUTER_API_KEY)
# - Deploy automático

# 3. ¡Listo! API en https://tu-api.up.railway.app
```

Ver [QUICK_START.md](QUICK_START.md) para instrucciones detalladas.

---

## 📡 Endpoints

### REST

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | GET | Verificar que API funciona |
| `/process_pdf` | POST | Procesar PDF completo |
| `/save_note` | POST | Guardar nota manual |
| `/docs` | GET | Documentación interactiva (Swagger) |

### WebSocket

```
ws://localhost:8000/ws
```

Flujo:
1. Autenticar: `{type: "auth", token: "..."}`
2. Enviar notas: `{tipo: "literatura", nombre: "...", contenido: "..."}`

---

## 🔧 Configuración

Variables de entorno (en `.env` local o Railway dashboard):

```ini
API_TOKEN=tu_token_secreto_aqui
OPENROUTER_API_KEY=sk-or-v1-... (obtén en openrouter.ai)
DEBUG=False
PORT=8000
```

---

## 📚 Documentación

- **[QUICK_START.md](QUICK_START.md)** - Inicio rápido (⭐ EMPIEZA AQUÍ)
- **[README_API.md](README_API.md)** - Guía de uso general
- **[API_USAGE.md](API_USAGE.md)** - Documentación completa de endpoints
- **[RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)** - Despliegue en Railway
- **[SETUP_CHECKLIST.md](SETUP_CHECKLIST.md)** - Checklist pre-deploy

---

## 🗂️ Estructura del Proyecto

```
agente_academico/
├── api.py                      # 🎯 API principal (FastAPI)
├── start_api.py                # Script para iniciar
├── test_api.py                 # Tests interactivos
├── main.py                     # Pipeline original
│
├── src/
│   ├── ai_processor.py         # Procesamiento con IA (OpenRouter)
│   ├── pdf_extracter.py        # Extrae PDFs (MinerU)
│   ├── markdown_cleaner.py     # Limpia markdown
│   └── obsidian_exporter.py    # Guarda en Obsidian
│
├── docker-compose.yml          # Docker Compose para desarrollo
├── Dockerfile                  # Dockerfile para Railway
├── railway.json                # Configuración Railway
│
├── requirements-api.txt        # Dependencias Python
├── .gitignore                  # Archivos a ignorar
│
└── docs/
    ├── README_API.md           # Uso general
    ├── API_USAGE.md            # Referencia completa
    ├── RAILWAY_DEPLOYMENT.md   # Deploy
    └── SETUP_CHECKLIST.md      # Checklist
```

---

## 🧪 Testing

```bash
# Menú interactivo
python test_api.py

# Tests específicos
python test_api.py health      # Health check
python test_api.py note        # Guardar nota
python test_api.py ws          # WebSocket
python test_api.py all         # Todos
```

---

## 🔐 Seguridad

- ✅ Token-based authentication
- ✅ Variables de entorno (nunca hardcodear secrets)
- ✅ `.env` en `.gitignore` (no se sube a Git)
- ✅ WebSocket Secure (`wss://`) en producción
- ✅ CORS configurable

---

## 🚀 Deployment

### Railway (Recomendado)

```bash
# 1. Conectar repo a https://railway.app
# 2. Setear variables de entorno
# 3. Auto-deploy en cada push

# Tu API estará en:
https://tu-app-xxxx.up.railway.app
```

### Docker Local

```bash
docker-compose up --build
# API en http://localhost:8000
```

---

## 📊 Flujo Completo

```
PDF (en n8n/Drive)
    ↓
[API /process_pdf]
    ├─ Extrae con MinerU
    ├─ Procesa con IA
    └─ Guarda 3 tipos de notas
    ↓
WebSocket → Obsidian Plugin
    ↓
Obsidian Vault
    ├─ Literatura/
    ├─ Atomicas/
    ├─ MOCs/
    └─ Fuentes/
```

---

## 🤝 Integración con n8n

En tu workflow n8n:
1. HTTP Request node → POST `/process_pdf`
2. URL: `https://tu-api-railway.up.railway.app/process_pdf`
3. Parámetro: `token=TU_TOKEN`
4. Body: `form-data` con PDF

---

## 🐛 Troubleshooting

| Problema | Solución |
|----------|----------|
| Port 8000 en uso | Cambiar: `PORT=8001 python start_api.py` |
| Token inválido | Verificar `.env` o Railway variables |
| WebSocket no conecta | Usar `wss://` en producción |
| MinerU error | `pip install mineru` |

Ver [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) para más.

---

## 📝 Licencia

MIT

---

## 👤 Autor

Creado para automatizar la gestión de conocimiento académico con Obsidian.

---

## 🎯 Next Steps

1. ⭐ Leer [QUICK_START.md](QUICK_START.md)
2. 🧪 Probar localmente: `python start_api.py`
3. 🚀 Deploy a Railway siguiendo [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)
4. 🔗 Conectar Obsidian plugin

---

**¡Listo para producción!** 🎉
