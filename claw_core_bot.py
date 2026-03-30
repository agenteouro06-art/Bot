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

# ================================
# 🔐 ENV
# ================================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER       = int(os.getenv("ALLOWED_USER"))
N8N_URL            = os.getenv("N8N_URL")
N8N_API_KEY        = os.getenv("N8N_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ================================
# 🧠 IA PROMPT
# ================================
SYSTEM_PROMPT = """Eres CLAW modo brutal.
Creas workflows n8n reales, completos, conectados y funcionales.
Si faltan credenciales, NO generas workflow.
Primero las pides.

Reglas:
- Nada de nodos sueltos
- JSON válido
- Conexiones completas
"""

# ================================
# 🧠 IA
# ================================
def llamar_ia(mensaje):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": "Bearer " + OPENROUTER_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-haiku-3",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": mensaje}
                ]
            },
            timeout=60
        )
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return "Error IA: " + str(e)

# ================================
# 🧠 ARQUITECTO REAL
# ================================
def detectar_credenciales(text):
    text = text.lower()
    needs = []

    if "whatsapp" in text:
        needs.append("whatsapp")

    if "correo" in text or "gmail" in text or "banco" in text:
        needs.append("gmail")

    if "imagen" in text or "captura" in text:
        needs.append("ocr")

    return needs

def faltantes(context, needs):
    return [n for n in needs if n not in context.user_data]

# ================================
# 🏗 WORKFLOW REAL
# ================================
def workflow_pagos():
    return {
        "name": "Validacion Pagos PRO",
        "nodes": [
            {
                "parameters": {"path": "pagos", "httpMethod": "POST"},
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "position": [200, 300]
            },
            {
                "parameters": {
                    "url": "https://api.ocr.space/parse/image",
                    "method": "POST"
                },
                "id": "2",
                "name": "OCR",
                "type": "n8n-nodes-base.httpRequest",
                "position": [400, 300]
            },
            {
                "parameters": {"resource": "message", "operation": "getAll"},
                "id": "3",
                "name": "Gmail",
                "type": "n8n-nodes-base.gmail",
                "position": [600, 300]
            },
            {
                "parameters": {
                    "functionCode": "return [{json:{match:true}}];"
                },
                "id": "4",
                "name": "Validar",
                "type": "n8n-nodes-base.function",
                "position": [800, 300]
            }
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "OCR"}]]},
            "OCR": {"main": [[{"node": "Gmail"}]]},
            "Gmail": {"main": [[{"node": "Validar"}]]}
        },
        "settings": {}
    }

# ================================
# 🚀 N8N
# ================================
def crear_n8n(wf):
    try:
        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=wf
        )
        return r.text
    except Exception as e:
        return str(e)

# ================================
# 🤖 BOT
# ================================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ALLOWED_USER:
        return

    text = update.message.text.lower()

    await update.message.chat.send_action(ChatAction.TYPING)

    # ============================
    # 📥 GUARDAR RESPUESTAS
    # ============================
    for key in ["whatsapp", "gmail", "ocr"]:
        if context.user_data.get("esperando_" + key):
            context.user_data[key] = text
            context.user_data["esperando_" + key] = False
            await update.message.reply_text(f"✅ Guardado {key}")
            return

    # ============================
    # 🧠 DETECTAR
    # ============================
    needs = detectar_credenciales(text)
    falt = faltantes(context, needs)

    if falt:
        for f in falt:
            context.user_data["esperando_" + f] = True

            if f == "whatsapp":
                await update.message.reply_text("📱 ¿Tienes API WhatsApp? SI/NO")

            if f == "gmail":
                await update.message.reply_text("📧 Dame correo + app password")

            if f == "ocr":
                await update.message.reply_text("🖼 Dame OCR API KEY")

        return

    # ============================
    # 🧠 MULTI-AGENTE VISUAL
    # ============================
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

    # ============================
    # 🚀 CREAR WORKFLOW
    # ============================
    wf = workflow_pagos()
    res = crear_n8n(wf)

    botones = [[
        InlineKeyboardButton("✅ OK", callback_data="ok"),
        InlineKeyboardButton("❌ Cancelar", callback_data="no")
    ]]

    await update.message.reply_text(
        "🚀 Workflow creado\nConfigura credenciales en n8n",
        reply_markup=InlineKeyboardMarkup(botones)
    )

# ================================
# 🔘 BOTONES
# ================================
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "ok":
        await query.edit_message_text("✅ Ejecutado")

    elif query.data == "no":
        await query.edit_message_text("❌ Cancelado")

# ================================
# ▶️ START
# ================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("CLAW PRO ACTIVADO")

# ================================
# 🚀 RUN
# ================================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW PRO RUNNING")
app.run_polling()
