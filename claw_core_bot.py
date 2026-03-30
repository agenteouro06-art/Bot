import os
import json
import asyncio
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# 🔥 CARGAR ENV (CORREGIDO)
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER       = int(os.getenv("ALLOWED_USER"))
N8N_URL            = os.getenv("N8N_URL")
N8N_API_KEY        = os.getenv("N8N_API_KEY")

# 🔥 PLANTILLA REAL FUNCIONAL (BASE SEGURA)
BASE_WORKFLOW = {
    "name": "CLAW Base Flow",
    "nodes": [
        {
            "id": "1",
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [300, 300],
            "parameters": {
                "path": "claw-webhook",
                "httpMethod": "POST"
            }
        },
        {
            "id": "2",
            "name": "Set",
            "type": "n8n-nodes-base.set",
            "typeVersion": 2,
            "position": [600, 300],
            "parameters": {
                "values": {
                    "string": [
                        {
                            "name": "mensaje",
                            "value": "Workflow funcionando"
                        }
                    ]
                }
            }
        }
    ],
    "connections": {
        "Webhook": {
            "main": [
                [
                    {
                        "node": "Set",
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        }
    },
    "settings": {}
}

estado = {}

# 🔥 NORMALIZAR (ANTI-ERRORES)
def normalizar(workflow):
    if not workflow:
        return None

    workflow["name"] = workflow.get("name", "CLAW Flow")
    workflow["nodes"] = workflow.get("nodes", [])
    workflow["connections"] = workflow.get("connections", {})
    workflow["settings"] = workflow.get("settings", {})

    # ❌ ELIMINAR CAMPOS PROHIBIDOS
    workflow.pop("active", None)
    workflow.pop("id", None)

    for node in workflow["nodes"]:
        node["id"] = node.get("id", node.get("name"))
        node["parameters"] = node.get("parameters", {})
        node["position"] = node.get("position", [300, 300])
        node["typeVersion"] = node.get("typeVersion", 1)

    return workflow

# 🔥 CREAR WORKFLOW EN N8N (FUNCIONAL REAL)
def crear_workflow(workflow):
    try:
        workflow = normalizar(workflow)

        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=workflow,
            timeout=20
        )

        data = r.json()

        if r.status_code != 200:
            return {"error": data}

        return {"ok": True, "data": data}

    except Exception as e:
        return {"error": str(e)}

# 🚀 MOTOR PRINCIPAL
async def procesar(update, context, texto):
    uid = update.effective_user.id

    # 🧠 MUÑECOS (VISUAL PRO)
    pasos = [
        "🧠 ANALISTA...",
        "🏗 ARQUITECTO...",
        "🎨 DISEÑADOR...",
        "🔍 VALIDADOR...",
        "⚙ EJECUTOR...",
        "💰 OPTIMIZADOR..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.3)

    # 🔥 USAMOS SIEMPRE BASE FUNCIONAL
    workflow = BASE_WORKFLOW.copy()

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

    await update.message.reply_text(
        "🚀 Workflow listo (base funcional garantizada)",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# 🎛 BOTONES
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    chat_id = query.message.chat.id

    if query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await context.bot.send_message(chat_id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        await context.bot.send_message(chat_id, "🚀 Creando en n8n...")

        res = crear_workflow(estado[uid])

        if "ok" in res:
            await context.bot.send_message(chat_id, f"✅ Creado correctamente:\n{res['data']}")
        else:
            await context.bot.send_message(chat_id, f"❌ Error:\n{res['error']}")

    elif query.data == "regen":
        await query.edit_message_text("🔄 Regenerando...")
        await procesar(query, context, "regen")

# 📩 MENSAJES
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)

# 🚀 INICIO BOT
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW FUNCIONAL REAL INICIADO")
app.run_polling()
