import os
import json
import time
import asyncio
import requests
from dotenv import load_dotenv
import anthropic

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

# ================================

# 🔐 ENV

# ================================

load_dotenv(”/home/mau/claw_core/.env”)

TELEGRAM_TOKEN   = os.getenv(“TELEGRAM_TOKEN”)
ALLOWED_USER     = int(os.getenv(“ALLOWED_USER”))
N8N_URL          = os.getenv(“N8N_URL”)          # ej: http://localhost:5678
N8N_API_KEY      = os.getenv(“N8N_API_KEY”)
ANTHROPIC_API_KEY = os.getenv(“ANTHROPIC_API_KEY”)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ================================

# 🧠 SISTEMA MULTI-AGENTE CON CLAUDE

# ================================

SYSTEM_PROMPT = “”“Eres CLAW, un sistema autónomo multi-agente especializado en automatización con n8n.

MENTALIDAD: Piensas como ingeniero. Construyes soluciones reales, no teoría.

AGENTES QUE EJECUTAS EN ORDEN:
[ANALISTA] → Detecta tipo de negocio, objetivo, integraciones necesarias
[ARQUITECTO] → Decide qué nodos n8n usar y cómo conectarlos
[DISEÑADOR] → Crea el JSON del workflow completo y válido
[VALIDADOR] → Verifica conexiones y lógica
[EJECUTOR] → Lista exacta de credenciales/APIs que faltan
[OPTIMIZADOR] → Simplifica y deja listo para producción/venta

REGLAS DE WORKFLOWS N8N:

- Siempre usa IDs únicos para cada nodo (id: “node_1”, “node_2”, etc.)
- SIEMPRE conecta los nodos en “connections” con el formato exacto de n8n
- Incluye lógica real en los nodos Function (no dejes código vacío)
- Usa typeVersion correcto: webhook=2, httpRequest=4.2, googleSheets=4, gmail=2.1, function=1
- Los nodos deben tener: id, name, type, typeVersion, position, parameters
- Las connections usan el nombre del nodo (name), NO el id

FORMATO DE RESPUESTA (siempre):
🧠 **ANÁLISIS**: [qué detectaste]
⚙️ **PLAN**: [qué vas a construir]  
🔧 **APIS NECESARIAS**: [lista de credenciales/keys que necesita el usuario]
🚀 **RESULTADO**: [descripción del workflow]
📋 **WORKFLOW_JSON**: [el JSON completo entre triple backticks]
💰 **VALOR COMERCIAL**: [precio estimado y a quién venderlo]

Si faltan credenciales/APIs del usuario, pregunta PRIMERO antes de generar el workflow.
Responde siempre en español.”””

async def ejecutar_multiagente(mensaje_usuario: str, credenciales_extra: str = “”) -> dict:
“”“Llama a Claude Haiku con el sistema multiagente y retorna análisis + workflow JSON”””

```
prompt = mensaje_usuario
if credenciales_extra:
    prompt += f"\n\nCREDENCIALES DISPONIBLES: {credenciales_extra}"

message = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=4096,
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": prompt}]
)

respuesta = message.content[0].text

# Extraer JSON del workflow si existe
workflow_json = None
if "```json" in respuesta or "```" in respuesta:
    try:
        # Buscar entre ```json ... ``` o ``` ... ```
        inicio = respuesta.find("```json")
        if inicio == -1:
            inicio = respuesta.find("```")
            contenido = respuesta[inicio+3:]
        else:
            contenido = respuesta[inicio+7:]
        
        fin = contenido.find("```")
        if fin != -1:
            json_str = contenido[:fin].strip()
            workflow_json = json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        workflow_json = None

# Limpiar el texto (quitar el bloque JSON para mostrarlo por separado)
texto_limpio = respuesta
if "```" in respuesta:
    partes = respuesta.split("```")
    texto_limpio = partes[0]
    if len(partes) > 2:
        texto_limpio += partes[-1]

return {
    "texto": texto_limpio.strip(),
    "workflow_json": workflow_json,
    "respuesta_completa": respuesta
}
```

# ================================

# 🚀 N8N API - OPERACIONES COMPLETAS

# ================================

def n8n_headers():
return {
“X-N8N-API-KEY”: N8N_API_KEY,
“Content-Type”: “application/json”
}

def crear_workflow_n8n(workflow: dict) -> dict:
“”“Crea un workflow en n8n vía API”””
try:
r = requests.post(
f”{N8N_URL}/api/v1/workflows”,
headers=n8n_headers(),
json=workflow,
timeout=15
)
r.raise_for_status()
return {“ok”: True, “data”: r.json()}
except requests.RequestException as e:
return {“ok”: False, “error”: str(e)}

def activar_workflow_n8n(workflow_id: str) -> dict:
“”“Activa un workflow en n8n”””
try:
r = requests.patch(
f”{N8N_URL}/api/v1/workflows/{workflow_id}”,
headers=n8n_headers(),
json={“active”: True},
timeout=10
)
r.raise_for_status()
return {“ok”: True}
except requests.RequestException as e:
return {“ok”: False, “error”: str(e)}

def ejecutar_workflow_n8n(workflow_id: str) -> dict:
“”“Ejecuta un workflow manualmente para probarlo”””
try:
r = requests.post(
f”{N8N_URL}/api/v1/workflows/{workflow_id}/run”,
headers=n8n_headers(),
timeout=30
)
r.raise_for_status()
return {“ok”: True, “data”: r.json()}
except requests.RequestException as e:
return {“ok”: False, “error”: str(e)}

def obtener_ejecuciones_n8n(workflow_id: str) -> dict:
“”“Obtiene el resultado de las últimas ejecuciones”””
try:
r = requests.get(
f”{N8N_URL}/api/v1/executions?workflowId={workflow_id}&limit=1”,
headers=n8n_headers(),
timeout=10
)
r.raise_for_status()
return {“ok”: True, “data”: r.json()}
except requests.RequestException as e:
return {“ok”: False, “error”: str(e)}

def listar_workflows_n8n() -> dict:
“”“Lista todos los workflows existentes”””
try:
r = requests.get(
f”{N8N_URL}/api/v1/workflows”,
headers=n8n_headers(),
timeout=10
)
r.raise_for_status()
return {“ok”: True, “data”: r.json()}
except requests.RequestException as e:
return {“ok”: False, “error”: str(e)}

def obtener_workflow_n8n(workflow_id: str) -> dict:
“”“Obtiene un workflow específico para clonar o modificar”””
try:
r = requests.get(
f”{N8N_URL}/api/v1/workflows/{workflow_id}”,
headers=n8n_headers(),
timeout=10
)
r.raise_for_status()
return {“ok”: True, “data”: r.json()}
except requests.RequestException as e:
return {“ok”: False, “error”: str(e)}

# ================================

# 💾 ESTADO DE CONVERSACIÓN

# ================================

# Guarda el contexto por usuario para manejo de credenciales pendientes

estado_conversacion: dict = {}

def guardar_estado(user_id: int, key: str, value):
if user_id not in estado_conversacion:
estado_conversacion[user_id] = {}
estado_conversacion[user_id][key] = value

def obtener_estado(user_id: int, key: str):
return estado_conversacion.get(user_id, {}).get(key)

def limpiar_estado(user_id: int):
if user_id in estado_conversacion:
del estado_conversacion[user_id]

# ================================

# 📤 HELPERS DE MENSAJES

# ================================

async def typing(update_or_query, context):
chat_id = (
update_or_query.effective_chat.id
if hasattr(update_or_query, “effective_chat”)
else update_or_query.message.chat.id
)
await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

async def enviar_largo(update, context, texto: str):
“”“Envía mensajes largos en chunks de 4000 chars”””
MAX = 4000
for i in range(0, len(texto), MAX):
await update.message.reply_text(texto[i:i+MAX])
await asyncio.sleep(0.3)

# ================================

# 🔥 FLUJO PRINCIPAL - CREAR WORKFLOW

# ================================

async def procesar_solicitud_workflow(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str, credenciales: str = “”):
user_id = update.effective_user.id
chat_id = update.effective_chat.id

```
await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
await update.message.reply_text("🧠 **CLAW ACTIVADO** — Sistema multiagente iniciando...", parse_mode="Markdown")

# Mensajes de agentes con delays realistas
agentes = [
    "🔍 **[ANALISTA]** Procesando solicitud...",
    "🏗 **[ARQUITECTO]** Diseñando arquitectura...",
    "🎨 **[DISEÑADOR]** Construyendo nodos y conexiones...",
    "✅ **[VALIDADOR]** Verificando lógica del flujo...",
    "⚙️ **[EJECUTOR]** Preparando integración...",
    "💰 **[OPTIMIZADOR]** Optimizando para producción...",
]

for msg in agentes:
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await update.message.reply_text(msg, parse_mode="Markdown")
    await asyncio.sleep(0.8)

# Llamar a Claude multiagente
await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
resultado = await ejecutar_multiagente(texto, credenciales)

# Enviar análisis y plan
if resultado["texto"]:
    await enviar_largo(update, context, resultado["texto"])

# Si hay workflow JSON válido
if resultado["workflow_json"]:
    workflow = resultado["workflow_json"]
    guardar_estado(user_id, "ultimo_workflow", workflow)
    guardar_estado(user_id, "solicitud_original", texto)
    
    # Botones de acción
    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear_workflow"),
            InlineKeyboardButton("🧪 Crear y Probar", callback_data="crear_y_probar"),
        ],
        [
            InlineKeyboardButton("📋 Ver JSON", callback_data="ver_json"),
            InlineKeyboardButton("🔄 Regenerar", callback_data="regenerar"),
        ]
    ]
    await update.message.reply_text(
        "✅ **Workflow generado** — ¿Qué hacemos?",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )
else:
    # Si no generó JSON, puede ser que pida credenciales
    guardar_estado(user_id, "solicitud_original", texto)
    kb = [[InlineKeyboardButton("🔄 Reintentar con contexto", callback_data="regenerar")]]
    await update.message.reply_text(
        "⚠️ No se generó JSON de workflow. Proporciona las credenciales/APIs que indica arriba y vuelve a intentarlo.",
        reply_markup=InlineKeyboardMarkup(kb)
    )
```

# ================================

# 🎯 HANDLER DE BOTONES

# ================================

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
query = update.callback_query
await query.answer()
user_id = query.from_user.id
chat_id = query.message.chat.id
data = query.data

```
await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

# ── CREAR WORKFLOW ──────────────────────────
if data in ("crear_workflow", "crear_y_probar"):
    workflow = obtener_estado(user_id, "ultimo_workflow")
    if not workflow:
        await query.edit_message_text("❌ No hay workflow en memoria. Genera uno primero.")
        return
    
    await query.edit_message_text("⏳ Creando workflow en n8n...")
    resultado = crear_workflow_n8n(workflow)
    
    if resultado["ok"]:
        wf_data = resultado["data"]
        wf_id = wf_data.get("id")
        wf_name = wf_data.get("name", "Sin nombre")
        guardar_estado(user_id, "ultimo_workflow_id", wf_id)
        
        msg = f"✅ **Workflow creado exitosamente**\n\n📋 Nombre: `{wf_name}`\n🆔 ID: `{wf_id}`\n🔗 URL: {N8N_URL}/workflow/{wf_id}"
        
        if data == "crear_y_probar":
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
            await probar_workflow(chat_id, wf_id, context)
        else:
            kb = [[
                InlineKeyboardButton("🧪 Probar ahora", callback_data="probar_ultimo"),
                InlineKeyboardButton("✅ Activar", callback_data="activar_ultimo"),
            ]]
            await context.bot.send_message(
                chat_id=chat_id, text=msg,
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Error al crear workflow:\n`{resultado['error']}`",
            parse_mode="Markdown"
        )

# ── PROBAR ÚLTIMO WORKFLOW ──────────────────
elif data == "probar_ultimo":
    wf_id = obtener_estado(user_id, "ultimo_workflow_id")
    if not wf_id:
        await query.edit_message_text("❌ No hay ID de workflow guardado.")
        return
    await query.edit_message_text(f"🧪 Probando workflow `{wf_id}`...", parse_mode="Markdown")
    await probar_workflow(chat_id, wf_id, context)

# ── ACTIVAR ÚLTIMO WORKFLOW ─────────────────
elif data == "activar_ultimo":
    wf_id = obtener_estado(user_id, "ultimo_workflow_id")
    if not wf_id:
        await query.edit_message_text("❌ No hay ID de workflow guardado.")
        return
    resultado = activar_workflow_n8n(wf_id)
    if resultado["ok"]:
        await query.edit_message_text(f"✅ Workflow `{wf_id}` **activado** y corriendo.", parse_mode="Markdown")
    else:
        await query.edit_message_text(f"❌ Error activando: `{resultado['error']}`", parse_mode="Markdown")

# ── VER JSON ────────────────────────────────
elif data == "ver_json":
    workflow = obtener_estado(user_id, "ultimo_workflow")
    if not workflow:
        await query.edit_message_text("❌ No hay workflow en memoria.")
        return
    json_str = json.dumps(workflow, indent=2, ensure_ascii=False)
    # Enviar en chunks si es largo
    MAX = 3900
    for i in range(0, len(json_str), MAX):
        chunk = json_str[i:i+MAX]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"```json\n{chunk}\n```",
            parse_mode="Markdown"
        )

# ── REGENERAR ───────────────────────────────
elif data == "regenerar":
    solicitud = obtener_estado(user_id, "solicitud_original")
    if not solicitud:
        await query.edit_message_text("❌ No hay solicitud guardada. Escribe tu solicitud de nuevo.")
        return
    await query.edit_message_text("🔄 Regenerando workflow...")
    # Crear un update simulado para reutilizar la función
    await procesar_solicitud_workflow(query, context, solicitud)

# ── LISTAR WORKFLOWS ────────────────────────
elif data == "listar_workflows":
    resultado = listar_workflows_n8n()
    if resultado["ok"]:
        workflows = resultado["data"].get("data", [])
        if not workflows:
            await query.edit_message_text("📭 No hay workflows en n8n.")
            return
        texto = "📋 **Workflows en n8n:**\n\n"
        for wf in workflows[:10]:
            estado = "🟢" if wf.get("active") else "🔴"
            texto += f"{estado} `{wf['id']}` — {wf['name']}\n"
        kb = []
        for wf in workflows[:5]:
            kb.append([InlineKeyboardButton(
                f"🔗 Clonar: {wf['name'][:30]}",
                callback_data=f"clonar_{wf['id']}"
            )])
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await query.edit_message_text(f"❌ Error: `{resultado['error']}`", parse_mode="Markdown")

# ── CLONAR WORKFLOW ─────────────────────────
elif data.startswith("clonar_"):
    wf_id = data.replace("clonar_", "")
    await query.edit_message_text(f"🔄 Clonando workflow `{wf_id}`...", parse_mode="Markdown")
    resultado = obtener_workflow_n8n(wf_id)
    if resultado["ok"]:
        wf_original = resultado["data"]
        wf_clon = wf_original.copy()
        wf_clon["name"] = f"[CLON] {wf_original.get('name', 'Workflow')}"
        wf_clon.pop("id", None)
        wf_clon.pop("createdAt", None)
        wf_clon.pop("updatedAt", None)
        wf_clon["active"] = False
        
        guardar_estado(user_id, "ultimo_workflow", wf_clon)
        kb = [[
            InlineKeyboardButton("🚀 Crear clon", callback_data="crear_workflow"),
            InlineKeyboardButton("📋 Ver JSON", callback_data="ver_json"),
        ]]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Workflow clonado en memoria.\nNombre: `{wf_clon['name']}`\n\n¿Qué hacemos?",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Error clonando: `{resultado['error']}`",
            parse_mode="Markdown"
        )
```

# ================================

# 🧪 PRUEBA AUTOMÁTICA DE WORKFLOW

# ================================

async def probar_workflow(chat_id: int, workflow_id: str, context: ContextTypes.DEFAULT_TYPE):
“”“Ejecuta el workflow y reporta el resultado”””
await context.bot.send_message(chat_id=chat_id, text=“🧪 Ejecutando prueba del workflow…”)

```
# Intentar ejecución manual
resultado = ejecutar_workflow_n8n(workflow_id)

await asyncio.sleep(3)  # Esperar que termine

# Ver resultado de ejecuciones
ejecuciones = obtener_ejecuciones_n8n(workflow_id)

if ejecuciones["ok"]:
    data = ejecuciones["data"].get("data", [])
    if data:
        ej = data[0]
        status = ej.get("status", "unknown")
        emoji = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
        duracion = ej.get("stoppedAt", "")
        
        msg = (
            f"{emoji} **Resultado de prueba**\n\n"
            f"📊 Estado: `{status}`\n"
            f"🆔 ID Ejecución: `{ej.get('id', 'N/A')}`\n"
            f"🔗 Ver en n8n: {N8N_URL}/workflow/{workflow_id}/executions"
        )
        
        if status == "error":
            msg += "\n\n⚠️ Revisa las credenciales y configuración en n8n."
        elif status == "success":
            msg += "\n\n🎉 ¡Workflow funciona correctamente!"
    else:
        msg = "⚠️ No se encontraron ejecuciones. El workflow puede requerir un trigger externo (Webhook)."
else:
    msg = f"⚠️ No se pudo verificar ejecución: `{ejecuciones.get('error', 'Error desconocido')}`"

kb = [[InlineKeyboardButton("✅ Activar workflow", callback_data="activar_ultimo")]]
await context.bot.send_message(
    chat_id=chat_id, text=msg,
    reply_markup=InlineKeyboardMarkup(kb),
    parse_mode="Markdown"
)
```

# ================================

# 🤖 HANDLER PRINCIPAL

# ================================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return

```
text = update.message.text.strip()
user_id = update.effective_user.id

# Detectar si está proporcionando credenciales como respuesta
estado = obtener_estado(user_id, "esperando_credenciales")
if estado:
    solicitud_original = obtener_estado(user_id, "solicitud_original")
    guardar_estado(user_id, "esperando_credenciales", False)
    await procesar_solicitud_workflow(update, context, solicitud_original, credenciales=text)
    return

# Procesar solicitud normal
await procesar_solicitud_workflow(update, context, text)
```

# ================================

# 📋 COMANDOS

# ================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
await update.message.reply_text(
“🤖 **CLAW v2.0 — Sistema Multiagente n8n**\n\n”
“Escríbeme qué flujo necesitas y lo construyo.\n\n”
“**Comandos:**\n”
“/workflows — Lista tus workflows en n8n\n”
“/clonar [id] — Clona un workflow existente\n”
“/probar [id] — Prueba un workflow\n”
“/activar [id] — Activa un workflow\n”
“/limpiar — Limpia el estado\n\n”
“**Ejemplo:**\n”
“*Crea un flujo para restaurante con menú en Google Sheets y pedidos por WhatsApp*”,
parse_mode=“Markdown”
)

async def cmd_workflows(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
resultado = listar_workflows_n8n()
if resultado[“ok”]:
workflows = resultado[“data”].get(“data”, [])
if not workflows:
await update.message.reply_text(“📭 No hay workflows en n8n todavía.”)
return
texto = “📋 **Workflows en n8n:**\n\n”
kb = []
for wf in workflows[:10]:
estado = “🟢” if wf.get(“active”) else “🔴”
texto += f”{estado} `{wf['id']}` — {wf[‘name’]}\n”
kb.append([InlineKeyboardButton(
f”🔗 Clonar: {wf[‘name’][:25]}”,
callback_data=f”clonar_{wf[‘id’]}”
)])
await update.message.reply_text(
texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode=“Markdown”
)
else:
await update.message.reply_text(f”❌ Error: `{resultado['error']}`”, parse_mode=“Markdown”)

async def cmd_clonar(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
args = context.args
if not args:
await update.message.reply_text(“Uso: /clonar [id_workflow]”)
return
wf_id = args[0]
user_id = update.effective_user.id
resultado = obtener_workflow_n8n(wf_id)
if resultado[“ok”]:
wf_original = resultado[“data”]
wf_clon = wf_original.copy()
wf_clon[“name”] = f”[CLON] {wf_original.get(‘name’, ‘Workflow’)}”
wf_clon.pop(“id”, None)
wf_clon.pop(“createdAt”, None)
wf_clon.pop(“updatedAt”, None)
wf_clon[“active”] = False
guardar_estado(user_id, “ultimo_workflow”, wf_clon)
kb = [[
InlineKeyboardButton(“🚀 Crear clon”, callback_data=“crear_workflow”),
InlineKeyboardButton(“📋 Ver JSON”, callback_data=“ver_json”),
]]
await update.message.reply_text(
f”✅ Workflow `{wf_original.get('name')}` listo para clonar.”,
reply_markup=InlineKeyboardMarkup(kb),
parse_mode=“Markdown”
)
else:
await update.message.reply_text(f”❌ Error: `{resultado['error']}`”, parse_mode=“Markdown”)

async def cmd_probar(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
args = context.args
if not args:
user_id = update.effective_user.id
wf_id = obtener_estado(user_id, “ultimo_workflow_id”)
if not wf_id:
await update.message.reply_text(“Uso: /probar [id_workflow]”)
return
else:
wf_id = args[0]
await probar_workflow(update.effective_chat.id, wf_id, context)

async def cmd_activar(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
args = context.args
if not args:
await update.message.reply_text(“Uso: /activar [id_workflow]”)
return
resultado = activar_workflow_n8n(args[0])
if resultado[“ok”]:
await update.message.reply_text(f”✅ Workflow `{args[0]}` activado.”, parse_mode=“Markdown”)
else:
await update.message.reply_text(f”❌ Error: `{resultado['error']}`”, parse_mode=“Markdown”)

async def cmd_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
limpiar_estado(update.effective_user.id)
await update.message.reply_text(“🧹 Estado limpiado.”)

# ================================

# ▶️ RUN

# ================================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Comandos

app.add_handler(CommandHandler(“start”,      cmd_start))
app.add_handler(CommandHandler(“workflows”,  cmd_workflows))
app.add_handler(CommandHandler(“clonar”,     cmd_clonar))
app.add_handler(CommandHandler(“probar”,     cmd_probar))
app.add_handler(CommandHandler(“activar”,    cmd_activar))
app.add_handler(CommandHandler(“limpiar”,    cmd_limpiar))

# Mensajes y botones

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print(“🤖 CLAW v2.0 iniciado”)
app.run_polling()
