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

# ✅ CORRECCIÓN IMPORTANTE (comillas normales)
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER       = int(os.getenv("ALLOWED_USER"))
N8N_URL            = os.getenv("N8N_URL")
N8N_API_KEY        = os.getenv("N8N_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# 🧠 PROMPT MEJORADO (modo arquitecto real)
SYSTEM_PROMPT = """
Eres CLAW PRO.

Especialista en crear workflows REALES para n8n.

REGLAS CRITICAS:
- SOLO JSON VALIDO
- SIN TEXTO FUERA DEL JSON
- TODOS LOS NODOS CONECTADOS
- USAR NODOS REALES DE N8N
- typeVersion correcto
- LISTO PARA IMPORTAR

SI FALLAS → REINTENTA HASTA LOGRAR JSON VALIDO
"""

# 🔥 IA
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

        if "choices" not in data:
            return {"texto": str(data), "workflow_json": None}

        respuesta = data["choices"][0]["message"]["content"]

    except Exception as e:
        return {"texto": str(e), "workflow_json": None}

    # 🔍 EXTRAER JSON
    try:
        inicio = respuesta.find("{")
        fin = respuesta.rfind("}") + 1
        json_str = respuesta[inicio:fin]
        workflow = json.loads(json_str)
        return {"texto": "JSON generado correctamente", "workflow_json": workflow}
    except:
        return {"texto": respuesta, "workflow_json": None}

# 🔥 VALIDADOR JSON
def validar_workflow(workflow):
    if not workflow:
        return False

    if "nodes" not in workflow or "connections" not in workflow:
        return False

    if len(workflow["nodes"]) < 2:
        return False

    return True

# 🔥 AUTO FIX BÁSICO
def auto_fix_workflow(workflow):
    if not workflow:
        return workflow

    for node in workflow.get("nodes", []):
        if "position" not in node:
            node["position"] = [300, 300]

    return workflow

# 🔥 CREAR EN N8N
def crear_workflow_n8n(workflow):
    try:
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

# 🚀 MOTOR PRINCIPAL
async def procesar(update, context, texto):
    uid = update.effective_user.id

    await update.message.reply_text("🧠 CLAW PRO activado...")

    # 🔥 PRIMER INTENTO
    resultado = llamar_ia(texto)

    # 🔥 MODO DIOS AUTOMÁTICO
    if not resultado["workflow_json"]:
        await update.message.reply_text("⚠ IA falló → activando MODO DIOS...")

        prompt = f"CREA UN WORKFLOW N8N FUNCIONAL: {texto}"
        resultado = llamar_ia(prompt)

    workflow = resultado["workflow_json"]

    # 🔥 VALIDACIÓN
    if not validar_workflow(workflow):
        await update.message.reply_text("⚠ Corrigiendo workflow...")
        workflow = auto_fix_workflow(workflow)

    if not workflow:
        await update.message.reply_text("❌ No se pudo generar workflow")
        return

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

    if uid not in estado:
        await query.edit_message_text("No hay workflow")
        return

    if query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await context.bot.send_message(chat_id=query.message.chat.id, text=f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        res = crear_workflow_n8n(estado[uid])
        await context.bot.send_message(chat_id=query.message.chat.id, text=f"Resultado: {res}")

    elif query.data == "regen":
        await query.edit_message_text("🔄 Regenerando...")
        await procesar(query, context, "Mejora el workflow anterior")

# 📩 MENSAJES
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)

# 🚀 INICIO
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW PRO RUNNING")
app.run_polling()
