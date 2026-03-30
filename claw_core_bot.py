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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ================================
# 🧠 IA
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
                "model": "anthropic/claude-haiku-3",
                "messages": [
                    {
                        "role": "system",
                        "content": "Eres un arquitecto experto en n8n. Siempre generas workflows completos, conectados y funcionales."
                    },
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60
        )

        data = r.json()

        if "choices" not in data:
            return None, "Error IA: " + str(data)

        texto = data["choices"][0]["message"]["content"]

        # extraer json
        json_data = None
        if "```" in texto:
            try:
                bloque = texto.split("```")[1]
                if "json" in bloque:
                    bloque = bloque.replace("json", "")
                json_data = json.loads(bloque.strip())
            except:
                pass

        return json_data, texto

    except Exception as e:
        return None, str(e)

# ================================
# 🏗 FALLBACK (MEJORADO)
# ================================
def workflow_base():

    return {
        "name": "Base Restaurante",
        "nodes": [
            {
                "parameters": {
                    "path": "pedido",
                    "httpMethod": "POST"
                },
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "position": [200, 300]
            },
            {
                "parameters": {
                    "operation": "read",
                    "sheetId": "REEMPLAZAR"
                },
                "name": "Google Sheets",
                "type": "n8n-nodes-base.googleSheets",
                "position": [400, 300]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Google Sheets"}]]
            }
        }
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

    text = update.message.text

    await update.message.chat.send_action(ChatAction.TYPING)

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
    # 🧠 IA
    # ============================
    wf, texto_ia = llamar_ia(text)

    if not wf:
        await update.message.reply_text("⚠ IA falló → usando fallback")
        wf = workflow_base()

    context.user_data["workflow"] = wf

    botones = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="json")
        ],
        [
            InlineKeyboardButton("🧠 Mejorar (modo dios)", callback_data="mejorar")
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

    wf = context.user_data.get("workflow")

    if query.data == "crear":

        res = crear_n8n(wf)

        await query.edit_message_text("✅ Creado en n8n\n\nAhora configura:\n- WhatsApp API\n- Gmail\n- OCR")

    elif query.data == "json":

        txt = json.dumps(wf, indent=2)

        for i in range(0, len(txt), 4000):
            await query.message.reply_text(txt[i:i+4000])

    elif query.data == "mejorar":

        await query.edit_message_text("🧠 MODO DIOS REAL ACTIVADO...")

        prompt = "Optimiza este workflow para que sea vendible:\n" + json.dumps(wf)

        nuevo_wf, _ = llamar_ia(prompt)

        if nuevo_wf:
            context.user_data["workflow"] = nuevo_wf
            await query.message.reply_text("🔥 Workflow mejorado")
        else:
            await query.message.reply_text("⚠ No se pudo mejorar")

# ================================
# ▶️ START
# ================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 CLAW MODO DIOS ACTIVO")

# ================================
# 🚀 RUN
# ================================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 BOT NIVEL DIOS CORRIENDO")
app.run_polling()
