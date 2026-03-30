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

# 🔥 CORRECCIÓN CLAVE (comillas normales)
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER       = int(os.getenv("ALLOWED_USER"))
N8N_URL            = os.getenv("N8N_URL")
N8N_API_KEY        = os.getenv("N8N_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ================================
# 🧠 PROMPT MULTI-AGENTE PRO
# ================================

SYSTEM_PROMPT = """
Eres CLAW, sistema multiagente experto en automatización con n8n.

AGENTES:
[ANALISTA] Entiende el negocio
[ARQUITECTO] Diseña estructura
[DISEÑADOR] Construye JSON completo
[VALIDADOR] Corrige errores
[EJECUTOR] Define APIs
[OPTIMIZADOR] Lo deja listo para vender

REGLAS:
- SIEMPRE devolver JSON válido
- TODOS los nodos conectados
- Usar typeVersion correcto
- Incluir lógica real
- NO dejar nodos sueltos

FORMATO:
Explica breve + JSON dentro de ```json
"""

# ================================
# 🤖 IA
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
        respuesta = data["choices"][0]["message"]["content"]

    except Exception as e:
        return {"texto": str(e), "json": None}

    # 🔍 EXTRAER JSON
    workflow_json = None
    try:
        if "```json" in respuesta:
            json_str = respuesta.split("```json")[1].split("```")[0]
            workflow_json = json.loads(json_str)
    except:
        pass

    return {"texto": respuesta, "json": workflow_json}


# ================================
# 🔗 N8N
# ================================

def headers():
    return {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }

def crear_workflow(workflow):
    try:
        r = requests.post(
            N8N_URL + "/api/v1/workflows",
            headers=headers(),
            json=workflow
        )
        return r.json()
    except Exception as e:
        return str(e)


# ================================
# 💾 MEMORIA
# ================================

estado = {}

def guardar(uid, key, val):
    if uid not in estado:
        estado[uid] = {}
    estado[uid][key] = val

def obtener(uid, key):
    return estado.get(uid, {}).get(key)


# ================================
# 🚀 BOT
# ================================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text
    uid = update.effective_user.id

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    # 🔥 MULTI AGENTE VISUAL
    pasos = [
        "🧠 ANALISTA...",
        "🏗 ARQUITECTO...",
        "🎨 DISEÑADOR...",
        "🔍 VALIDADOR...",
        "⚙️ EJECUTOR...",
        "💰 OPTIMIZADOR..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.4)

    # 🤖 IA
    resultado = llamar_ia(texto)

    await update.message.reply_text("🧠 Resultado:")
    await update.message.reply_text(resultado["texto"][:4000])

    if resultado["json"]:
        guardar(uid, "wf", resultado["json"])

        botones = [
            [
                InlineKeyboardButton("🚀 Crear", callback_data="crear"),
                InlineKeyboardButton("👁 Ver JSON", callback_data="json")
            ]
        ]

        await update.message.reply_text(
            "¿Qué hacemos?",
            reply_markup=InlineKeyboardMarkup(botones)
        )
    else:
        await update.message.reply_text("❌ No se generó JSON")


# ================================
# 🔘 BOTONES
# ================================

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    if data == "crear":
        wf = obtener(uid, "wf")

        if not wf:
            await query.edit_message_text("No hay workflow")
            return

        res = crear_workflow(wf)

        await query.edit_message_text("🚀 Workflow creado en n8n")

    elif data == "json":
        wf = obtener(uid, "wf")

        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="```json\n" + json.dumps(wf, indent=2) + "\n```",
            parse_mode="Markdown"
        )


# ================================
# ▶️ START
# ================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 CLAW PRO ACTIVADO")


# ================================
# ▶️ RUN
# ================================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW PRO CORRIENDO...")
app.run_polling()
