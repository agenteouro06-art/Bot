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

# ✅ FIX COMILLAS (ERROR ORIGINAL)
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ================================
# 🧠 PROMPT MODO BRUTAL
# ================================
SYSTEM_PROMPT = """
Eres CLAW, sistema experto en automatización con n8n.

Debes:
- Crear workflows COMPLETOS
- Conectar TODOS los nodos
- No dejar nodos sueltos
- Usar nodos reales de n8n

Formato:
1. Explicación corta
2. JSON entre ```json ... ```
"""

# ================================
# 🤖 IA (ARREGLADA)
# ================================
def llamar_ia(prompt):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60
        )

        data = r.json()

        # 🔥 FIX ERROR 'choices'
        if "choices" not in data:
            return {"texto": str(data), "workflow_json": None}

        respuesta = data["choices"][0]["message"]["content"]

    except Exception as e:
        return {"texto": f"Error IA: {e}", "workflow_json": None}

    # 🔥 EXTRAER JSON
    workflow_json = None
    try:
        if "```json" in respuesta:
            json_str = respuesta.split("```json")[1].split("```")[0]
            workflow_json = json.loads(json_str)
    except:
        workflow_json = None

    return {"texto": respuesta, "workflow_json": workflow_json}

# ================================
# 🔥 FALLBACK (SI IA FALLA)
# ================================
def workflow_fallback():
    return {
        "name": "Fallback Restaurante",
        "nodes": [
            {
                "parameters": {"path": "pedido", "httpMethod": "POST"},
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300]
            },
            {
                "parameters": {"operation": "read", "sheetId": "ID"},
                "id": "2",
                "name": "Google Sheets",
                "type": "n8n-nodes-base.googleSheets",
                "typeVersion": 4,
                "position": [400, 300]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Google Sheets", "type": "main", "index": 0}]]
            }
        }
    }

# ================================
# 🚀 CREAR EN N8N
# ================================
def crear_workflow_n8n(workflow):
    try:
        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=workflow,
            timeout=15
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# ================================
# 🧠 MEMORIA
# ================================
estado = {}

def guardar(uid, key, value):
    if uid not in estado:
        estado[uid] = {}
    estado[uid][key] = value

def obtener(uid, key):
    return estado.get(uid, {}).get(key)

# ================================
# 🤖 BOT
# ================================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    # 🔥 ESCRIBIENDO
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    fases = [
        "🧠 ANALISTA...",
        "🏗 ARQUITECTO...",
        "🎨 DISEÑADOR...",
        "🔍 VALIDADOR...",
        "⚙️ EJECUTOR...",
        "💰 OPTIMIZADOR..."
    ]

    for f in fases:
        await update.message.reply_text(f)
        await asyncio.sleep(0.3)

    resultado = llamar_ia(texto)

    if resultado["texto"]:
        await update.message.reply_text(resultado["texto"][:3000])

    if resultado["workflow_json"]:
        wf = resultado["workflow_json"]
    else:
        await update.message.reply_text("⚠ IA falló → usando fallback")
        wf = workflow_fallback()

    guardar(uid, "wf", wf)

    botones = [
        [
            InlineKeyboardButton("Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("Ver JSON", callback_data="json")
        ]
    ]

    await update.message.reply_text(
        "🚀 Workflow listo ¿Qué deseas hacer?",
        reply_markup=InlineKeyboardMarkup(botones)
    )

# ================================
# 🔘 BOTONES
# ================================
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    wf = obtener(uid, "wf")

    if not wf:
        await query.edit_message_text("No hay workflow")
        return

    if query.data == "crear":
        res = crear_workflow_n8n(wf)
        await query.edit_message_text("✅ Creado en n8n")

    elif query.data == "json":
        txt = json.dumps(wf, indent=2, ensure_ascii=False)
        await query.message.reply_text(f"```json\n{txt[:3900]}\n```")

# ================================
# ▶️ START
# ================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 CLAW listo (modo brutal)")

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 BOT ACTIVO")
app.run_polling()
