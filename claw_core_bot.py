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
    filters
)

load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER       = int(os.getenv("ALLOWED_USER"))
N8N_URL            = os.getenv("N8N_URL")
N8N_API_KEY        = os.getenv("N8N_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# 🔥 PLANTILLAS BASE (tipo marketplace)
PLANTILLAS = {
    "whatsapp_ocr": {
        "name": "WhatsApp OCR Base",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [300, 300],
                "parameters": {
                    "path": "whatsapp-in",
                    "httpMethod": "POST"
                }
            },
            {
                "id": "2",
                "name": "HTTP OCR",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4,
                "position": [600, 300],
                "parameters": {
                    "url": "https://api.ocr.space/parse/image",
                    "method": "POST"
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "HTTP OCR", "type": "main", "index": 0}]]
            }
        },
        "settings": {},
        "active": False
    }
}

# 🧠 IA (SOLO ADAPTA, NO INVENTA)
def llamar_ia(prompt, base):
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
                    {"role": "system", "content": "Modifica el JSON sin romper estructura de n8n"},
                    {"role": "user", "content": f"BASE:\n{json.dumps(base)}\n\nOBJETIVO:\n{prompt}"}
                ]
            }
        )

        data = r.json()
        if "choices" not in data:
            return None

        txt = data["choices"][0]["message"]["content"]

        inicio = txt.find("{")
        fin = txt.rfind("}") + 1
        return json.loads(txt[inicio:fin])

    except:
        return None

# 🔥 NORMALIZADOR PRO
def normalizar(workflow):
    if not workflow:
        return None

    workflow.setdefault("name", "CLAW Flow")
    workflow.setdefault("nodes", [])
    workflow.setdefault("connections", {})
    workflow.setdefault("settings", {})
    workflow.setdefault("active", False)

    for node in workflow["nodes"]:
        node.setdefault("id", node.get("name"))
        node.setdefault("parameters", {})
        node.setdefault("position", [300, 300])
        node.setdefault("typeVersion", 1)

    return workflow

# 🔥 CREAR EN N8N
def crear(workflow):
    try:
        workflow = normalizar(workflow)

        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=workflow
        )

        return r.json()
    except Exception as e:
        return {"error": str(e)}

estado = {}

# 🚀 MOTOR
async def procesar(update, context, texto):
    uid = update.effective_user.id

    await update.message.reply_text("🧠 ANALISTA...")
    await asyncio.sleep(0.3)
    await update.message.reply_text("🏗 ARQUITECTO...")
    await asyncio.sleep(0.3)
    await update.message.reply_text("🎨 DISEÑADOR...")
    await asyncio.sleep(0.3)
    await update.message.reply_text("🔍 VALIDADOR...")
    await asyncio.sleep(0.3)
    await update.message.reply_text("⚙ EJECUTOR...")
    await asyncio.sleep(0.3)
    await update.message.reply_text("💰 OPTIMIZADOR...")

    # 🔥 SELECCIÓN DE PLANTILLA
    if "whatsapp" in texto.lower():
        base = PLANTILLAS["whatsapp_ocr"]
    else:
        base = list(PLANTILLAS.values())[0]

    # 🔥 IA ADAPTA (NO CREA)
    workflow = llamar_ia(texto, base)

    # 🔥 FALLBACK REAL
    if not workflow:
        await update.message.reply_text("⚠ IA falló → usando plantilla base")
        workflow = base

    workflow = normalizar(workflow)

    estado[uid] = workflow

    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="ver")
        ],
        [
            InlineKeyboardButton("🔄 Regenerar", callback_data="regen")
        ]
    ]

    await update.message.reply_text("🚀 Workflow listo", reply_markup=InlineKeyboardMarkup(kb))

# 🎛 BOTONES
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    if query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await context.bot.send_message(query.message.chat.id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        res = crear(estado[uid])
        await context.bot.send_message(query.message.chat.id, f"Resultado:\n{res}")

    elif query.data == "regen":
        await query.edit_message_text("🔄 Regenerando...")
        await procesar(query, context, "Mejora el flujo")

# 📩 MENSAJES
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)

# 🚀 INICIO
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW MARKETPLACE MODE")
app.run_polling()
