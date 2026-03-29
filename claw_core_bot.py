import os
import json
import asyncio
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
ApplicationBuilder,
MessageHandler,
ContextTypes,
CallbackQueryHandler,
CommandHandler,
filters
)

load_dotenv(”/home/mau/claw_core/.env”)

TELEGRAM_TOKEN     = os.getenv(“TELEGRAM_TOKEN”)
ALLOWED_USER       = int(os.getenv(“ALLOWED_USER”))
N8N_URL            = os.getenv(“N8N_URL”)
N8N_API_KEY        = os.getenv(“N8N_API_KEY”)
OPENROUTER_API_KEY = os.getenv(“OPENROUTER_API_KEY”)

SYSTEM_PROMPT = “”“Eres CLAW, sistema multiagente especializado en automatización con n8n.

AGENTES QUE EJECUTAS:
[ANALISTA] Detecta tipo de negocio y objetivo
[ARQUITECTO] Decide nodos n8n y conexiones
[DISEÑADOR] Crea el JSON completo del workflow
[VALIDADOR] Verifica conexiones y lógica
[EJECUTOR] Lista APIs y credenciales faltantes
[OPTIMIZADOR] Deja el flujo listo para venta

REGLAS CRITICAS PARA EL JSON:

- Cada nodo debe tener: id, name, type, typeVersion, position, parameters
- typeVersion correcto: webhook=2, httpRequest=4.2, googleSheets=4, gmail=2.1, code=2
- Las connections usan el campo “name” del nodo, NO el id
- SIEMPRE conecta TODOS los nodos en “connections”
- Incluye logica real en nodos Code
- El JSON debe ser valido e importable directamente en n8n

FORMATO DE RESPUESTA:

1. Analisis corto de lo que detectaste
1. Plan de construccion
1. APIs y credenciales necesarias
1. Descripcion del workflow
1. Valor comercial estimado
1. El JSON completo entre `json y `

Si faltan credenciales, pideselas al usuario ANTES de generar.
Responde siempre en español.”””

def llamar_ia(mensaje: str, credenciales: str = “”) -> dict:
prompt = mensaje
if credenciales:
prompt += f”\n\nCREDENCIALES DISPONIBLES: {credenciales}”

```
try:
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/agenteouro06-art/Bot",
            "X-Title": "CLAW Bot"
        },
        json={
            "model": "anthropic/claude-haiku-3",
            "max_tokens": 4096,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        },
        timeout=60
    )
    r.raise_for_status()
    data = r.json()
    respuesta = data["choices"][0]["message"]["content"]
except Exception as e:
    return {"texto": f"Error llamando a la IA: {e}", "workflow_json": None}

workflow_json = None
try:
    inicio = respuesta.find("```json")
    if inicio == -1:
        inicio = respuesta.find("```")
        contenido = respuesta[inicio + 3:]
    else:
        contenido = respuesta[inicio + 7:]
    fin = contenido.find("```")
    if fin != -1:
        json_str = contenido[:fin].strip()
        workflow_json = json.loads(json_str)
except Exception:
    workflow_json = None

texto_limpio = respuesta
if "```" in respuesta:
    partes = respuesta.split("```")
    texto_limpio = partes[0]
    if len(partes) > 2:
        texto_limpio += partes[-1]

return {"texto": texto_limpio.strip(), "workflow_json": workflow_json}
```

# ── N8N ──────────────────────────────────────────────

def n8n_headers():
return {“X-N8N-API-KEY”: N8N_API_KEY, “Content-Type”: “application/json”}

def crear_workflow_n8n(workflow: dict) -> dict:
try:
r = requests.post(f”{N8N_URL}/api/v1/workflows”, headers=n8n_headers(), json=workflow, timeout=15)
r.raise_for_status()
return {“ok”: True, “data”: r.json()}
except Exception as e:
return {“ok”: False, “error”: str(e)}

def activar_workflow_n8n(wf_id: str) -> dict:
try:
r = requests.patch(f”{N8N_URL}/api/v1/workflows/{wf_id}”, headers=n8n_headers(), json={“active”: True}, timeout=10)
r.raise_for_status()
return {“ok”: True}
except Exception as e:
return {“ok”: False, “error”: str(e)}

def ejecutar_workflow_n8n(wf_id: str) -> dict:
try:
r = requests.post(f”{N8N_URL}/api/v1/workflows/{wf_id}/run”, headers=n8n_headers(), timeout=30)
r.raise_for_status()
return {“ok”: True, “data”: r.json()}
except Exception as e:
return {“ok”: False, “error”: str(e)}

def obtener_ejecuciones_n8n(wf_id: str) -> dict:
try:
r = requests.get(f”{N8N_URL}/api/v1/executions?workflowId={wf_id}&limit=1”, headers=n8n_headers(), timeout=10)
r.raise_for_status()
return {“ok”: True, “data”: r.json()}
except Exception as e:
return {“ok”: False, “error”: str(e)}

def listar_workflows_n8n() -> dict:
try:
r = requests.get(f”{N8N_URL}/api/v1/workflows”, headers=n8n_headers(), timeout=10)
r.raise_for_status()
return {“ok”: True, “data”: r.json()}
except Exception as e:
return {“ok”: False, “error”: str(e)}

def obtener_workflow_n8n(wf_id: str) -> dict:
try:
r = requests.get(f”{N8N_URL}/api/v1/workflows/{wf_id}”, headers=n8n_headers(), timeout=10)
r.raise_for_status()
return {“ok”: True, “data”: r.json()}
except Exception as e:
return {“ok”: False, “error”: str(e)}

# ── ESTADO ───────────────────────────────────────────

estado_conversacion: dict = {}

def guardar_estado(uid: int, key: str, value):
if uid not in estado_conversacion:
estado_conversacion[uid] = {}
estado_conversacion[uid][key] = value

def obtener_estado(uid: int, key: str):
return estado_conversacion.get(uid, {}).get(key)

def limpiar_estado(uid: int):
estado_conversacion.pop(uid, None)

# ── HELPERS ──────────────────────────────────────────

async def enviar_largo(update, context, texto: str):
MAX = 4000
for i in range(0, len(texto), MAX):
await update.message.reply_text(texto[i:i + MAX])
await asyncio.sleep(0.3)

async def probar_workflow(chat_id: int, wf_id: str, context):
await context.bot.send_message(chat_id=chat_id, text=“Ejecutando prueba del workflow…”)
ejecutar_workflow_n8n(wf_id)
await asyncio.sleep(3)
ejecuciones = obtener_ejecuciones_n8n(wf_id)
if ejecuciones[“ok”]:
data = ejecuciones[“data”].get(“data”, [])
if data:
ej = data[0]
status = ej.get(“status”, “unknown”)
emoji = “OK” if status == “success” else “ERROR” if status == “error” else “PENDIENTE”
msg = f”{emoji} - Estado: {status}\nVer en n8n: {N8N_URL}/workflow/{wf_id}/executions”
if status == “error”:
msg += “\n\nRevisa las credenciales en n8n.”
elif status == “success”:
msg += “\n\nEl workflow funciona correctamente.”
else:
msg = “Sin ejecuciones registradas. El workflow puede necesitar un Webhook externo para activarse.”
else:
msg = f”No se pudo verificar la ejecucion: {ejecuciones.get(‘error’, ‘’)}”
kb = [[InlineKeyboardButton(“Activar workflow”, callback_data=“activar_ultimo”)]]
await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=InlineKeyboardMarkup(kb))

# ── FLUJO PRINCIPAL ───────────────────────────────────

async def procesar_solicitud(update: Update, context, texto: str, credenciales: str = “”):
uid = update.effective_user.id
chat_id = update.effective_chat.id
await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
await update.message.reply_text(“CLAW activado — Sistema multiagente iniciando…”)

```
agentes = [
    "[ANALISTA] Procesando solicitud...",
    "[ARQUITECTO] Disenando arquitectura...",
    "[DISENADOR] Construyendo nodos y conexiones...",
    "[VALIDADOR] Verificando logica del flujo...",
    "[EJECUTOR] Preparando integracion...",
    "[OPTIMIZADOR] Optimizando para produccion...",
]
for msg in agentes:
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await update.message.reply_text(msg)
    await asyncio.sleep(0.6)

await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
resultado = llamar_ia(texto, credenciales)

if resultado["texto"]:
    await enviar_largo(update, context, resultado["texto"])

if resultado["workflow_json"]:
    guardar_estado(uid, "ultimo_workflow", resultado["workflow_json"])
    guardar_estado(uid, "solicitud_original", texto)
    kb = [
        [
            InlineKeyboardButton("Crear en n8n", callback_data="crear_workflow"),
            InlineKeyboardButton("Crear y Probar", callback_data="crear_y_probar"),
        ],
        [
            InlineKeyboardButton("Ver JSON", callback_data="ver_json"),
            InlineKeyboardButton("Regenerar", callback_data="regenerar"),
        ]
    ]
    await update.message.reply_text("Workflow generado. Que hacemos?", reply_markup=InlineKeyboardMarkup(kb))
else:
    guardar_estado(uid, "solicitud_original", texto)
    guardar_estado(uid, "esperando_credenciales", True)
    await update.message.reply_text(
        "No se genero JSON. Proporciona las credenciales o APIs indicadas arriba y escribelas aqui."
    )
```

# ── BOTONES ───────────────────────────────────────────

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
query = update.callback_query
await query.answer()
uid = query.from_user.id
chat_id = query.message.chat.id
data = query.data
await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

```
if data in ("crear_workflow", "crear_y_probar"):
    workflow = obtener_estado(uid, "ultimo_workflow")
    if not workflow:
        await query.edit_message_text("No hay workflow en memoria. Genera uno primero.")
        return
    await query.edit_message_text("Creando workflow en n8n...")
    resultado = crear_workflow_n8n(workflow)
    if resultado["ok"]:
        wf = resultado["data"]
        wf_id = wf.get("id")
        guardar_estado(uid, "ultimo_workflow_id", wf_id)
        msg = f"Workflow creado: {wf.get('name', 'Sin nombre')}\nID: {wf_id}\nURL: {N8N_URL}/workflow/{wf_id}"
        if data == "crear_y_probar":
            await context.bot.send_message(chat_id=chat_id, text=msg)
            await probar_workflow(chat_id, wf_id, context)
        else:
            kb = [[
                InlineKeyboardButton("Probar", callback_data="probar_ultimo"),
                InlineKeyboardButton("Activar", callback_data="activar_ultimo")
            ]]
            await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await context.bot.send_message(chat_id=chat_id, text=f"Error al crear: {resultado['error']}")

elif data == "probar_ultimo":
    wf_id = obtener_estado(uid, "ultimo_workflow_id")
    if not wf_id:
        await query.edit_message_text("No hay workflow guardado.")
        return
    await query.edit_message_text("Probando workflow...")
    await probar_workflow(chat_id, wf_id, context)

elif data == "activar_ultimo":
    wf_id = obtener_estado(uid, "ultimo_workflow_id")
    if not wf_id:
        await query.edit_message_text("No hay ID guardado.")
        return
    r = activar_workflow_n8n(wf_id)
    if r["ok"]:
        await query.edit_message_text(f"Workflow {wf_id} activado correctamente.")
    else:
        await query.edit_message_text(f"Error activando: {r['error']}")

elif data == "ver_json":
    workflow = obtener_estado(uid, "ultimo_workflow")
    if not workflow:
        await query.edit_message_text("No hay workflow en memoria.")
        return
    json_str = json.dumps(workflow, indent=2, ensure_ascii=False)
    for i in range(0, len(json_str), 3900):
        chunk = json_str[i:i + 3900]
        await context.bot.send_message(chat_id=chat_id, text=f"```json\n{chunk}\n```", parse_mode="Markdown")

elif data == "regenerar":
    solicitud = obtener_estado(uid, "solicitud_original")
    if not solicitud:
        await query.edit_message_text("No hay solicitud guardada. Escribe tu solicitud de nuevo.")
        return
    await query.edit_message_text("Regenerando workflow...")
    await procesar_solicitud(query, context, solicitud)

elif data == "listar_workflows":
    resultado = listar_workflows_n8n()
    if resultado["ok"]:
        workflows = resultado["data"].get("data", [])
        if not workflows:
            await query.edit_message_text("No hay workflows en n8n.")
            return
        texto = "Workflows en n8n:\n\n"
        kb = []
        for wf in workflows[:10]:
            estado = "ACTIVO" if wf.get("active") else "INACTIVO"
            texto += f"[{estado}] {wf['id']} - {wf['name']}\n"
            kb.append([InlineKeyboardButton(f"Clonar: {wf['name'][:25]}", callback_data=f"clonar_{wf['id']}")])
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await query.edit_message_text(f"Error: {resultado['error']}")

elif data.startswith("clonar_"):
    wf_id = data.replace("clonar_", "")
    resultado = obtener_workflow_n8n(wf_id)
    if resultado["ok"]:
        wf_original = resultado["data"]
        wf_clon = wf_original.copy()
        wf_clon["name"] = f"[CLON] {wf_original.get('name', 'Workflow')}"
        for campo in ["id", "createdAt", "updatedAt"]:
            wf_clon.pop(campo, None)
        wf_clon["active"] = False
        guardar_estado(uid, "ultimo_workflow", wf_clon)
        kb = [[
            InlineKeyboardButton("Crear clon", callback_data="crear_workflow"),
            InlineKeyboardButton("Ver JSON", callback_data="ver_json")
        ]]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Listo para clonar: {wf_clon['name']}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    else:
        await context.bot.send_message(chat_id=chat_id, text=f"Error clonando: {resultado['error']}")
```

# ── HANDLER PRINCIPAL ─────────────────────────────────

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
texto = update.message.text.strip()
uid = update.effective_user.id
if obtener_estado(uid, “esperando_credenciales”):
solicitud = obtener_estado(uid, “solicitud_original”)
guardar_estado(uid, “esperando_credenciales”, False)
await procesar_solicitud(update, context, solicitud, credenciales=texto)
return
await procesar_solicitud(update, context, texto)

# ── COMANDOS ──────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
await update.message.reply_text(
“CLAW v2.0 - Sistema Multiagente n8n\n\n”
“Escríbeme qué flujo necesitas y lo construyo.\n\n”
“Comandos:\n”
“/workflows - Lista tus workflows en n8n\n”
“/clonar [id] - Clona un workflow existente\n”
“/probar [id] - Prueba un workflow\n”
“/activar [id] - Activa un workflow\n”
“/limpiar - Limpia el estado\n\n”
“Ejemplo:\n”
“Crea un flujo para restaurante con menu en Google Sheets y pedidos por WhatsApp”
)

async def cmd_workflows(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
resultado = listar_workflows_n8n()
if resultado[“ok”]:
workflows = resultado[“data”].get(“data”, [])
if not workflows:
await update.message.reply_text(“No hay workflows en n8n todavia.”)
return
texto = “Workflows en n8n:\n\n”
kb = []
for wf in workflows[:10]:
estado = “ACTIVO” if wf.get(“active”) else “INACTIVO”
texto += f”[{estado}] {wf[‘id’]} - {wf[‘name’]}\n”
kb.append([InlineKeyboardButton(f”Clonar: {wf[‘name’][:25]}”, callback_data=f”clonar_{wf[‘id’]}”)])
await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(kb))
else:
await update.message.reply_text(f”Error: {resultado[‘error’]}”)

async def cmd_clonar(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
if not context.args:
await update.message.reply_text(“Uso: /clonar [id_workflow]”)
return
wf_id = context.args[0]
uid = update.effective_user.id
resultado = obtener_workflow_n8n(wf_id)
if resultado[“ok”]:
wf_original = resultado[“data”]
wf_clon = wf_original.copy()
wf_clon[“name”] = f”[CLON] {wf_original.get(‘name’, ‘Workflow’)}”
for campo in [“id”, “createdAt”, “updatedAt”]:
wf_clon.pop(campo, None)
wf_clon[“active”] = False
guardar_estado(uid, “ultimo_workflow”, wf_clon)
kb = [[
InlineKeyboardButton(“Crear clon”, callback_data=“crear_workflow”),
InlineKeyboardButton(“Ver JSON”, callback_data=“ver_json”)
]]
await update.message.reply_text(
f”Listo para clonar: {wf_clon[‘name’]}”,
reply_markup=InlineKeyboardMarkup(kb)
)
else:
await update.message.reply_text(f”Error: {resultado[‘error’]}”)

async def cmd_probar(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
uid = update.effective_user.id
wf_id = context.args[0] if context.args else obtener_estado(uid, “ultimo_workflow_id”)
if not wf_id:
await update.message.reply_text(“Uso: /probar [id_workflow]”)
return
await probar_workflow(update.effective_chat.id, wf_id, context)

async def cmd_activar(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
if not context.args:
await update.message.reply_text(“Uso: /activar [id_workflow]”)
return
r = activar_workflow_n8n(context.args[0])
if r[“ok”]:
await update.message.reply_text(f”Workflow {context.args[0]} activado.”)
else:
await update.message.reply_text(f”Error: {r[‘error’]}”)

async def cmd_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
limpiar_estado(update.effective_user.id)
await update.message.reply_text(“Estado limpiado.”)

# ── RUN ───────────────────────────────────────────────

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler(“start”,     cmd_start))
app.add_handler(CommandHandler(“workflows”, cmd_workflows))
app.add_handler(CommandHandler(“clonar”,    cmd_clonar))
app.add_handler(CommandHandler(“probar”,    cmd_probar))
app.add_handler(CommandHandler(“activar”,   cmd_activar))
app.add_handler(CommandHandler(“limpiar”,   cmd_limpiar))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print(“CLAW v2.0 iniciado con OpenRouter”)
app.run_polling()
