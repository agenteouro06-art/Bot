import os
import json
import asyncio
import requests
import copy
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# 🔥 ENV
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

estado = {}

# 🔥 BASE MEJORADA (NO SOLO 2 NODOS)
def generar_workflow_base():
    return {
        "name": "CLAW Smart Flow",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "claw-webhook",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },
            {
                "id": "2",
                "name": "Set Inicial",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [400, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "status", "value": "recibido"}
                        ]
                    }
                }
            },
            {
                "id": "3",
                "name": "Function Procesar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [600, 300],
                "parameters": {
                    "functionCode": "return items.map(item => { item.json.procesado = true; return item; });"
                }
            },
            {
                "id": "4",
                "name": "Set Final",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [800, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "resultado", "value": "ok"}
                        ]
                    }
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Set Inicial", "type": "main", "index": 0}]]
            },
            "Set Inicial": {
                "main": [[{"node": "Function Procesar", "type": "main", "index": 0}]]
            },
            "Function Procesar": {
                "main": [[{"node": "Set Final", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }

# 🔥 NORMALIZAR
def normalizar(workflow):
    workflow["name"] = workflow.get("name", "CLAW Flow")
    workflow["nodes"] = workflow.get("nodes", [])
    workflow["connections"] = workflow.get("connections", {})
    workflow["settings"] = workflow.get("settings", {})

    workflow.pop("active", None)
    workflow.pop("id", None)

    for node in workflow["nodes"]:
        node["id"] = str(node.get("id", node.get("name")))
        node["parameters"] = node.get("parameters", {})
        node["position"] = node.get("position", [300, 300])
        node["typeVersion"] = node.get("typeVersion", 1)

    return workflow

# 🔥 CREAR EN N8N
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

        return r.json()

    except Exception as e:
        return {"error": str(e)}

# 🚀 MOTOR
async def procesar(update, context, texto):
    uid = update.effective_user.id

    pasos = [
        "🧠 ANALISTA...",
        "🏗 ARQUITECTO...",
        "🎨 DISEÑADOR...",
        "🔍 VALIDADOR...",
        "⚙ EJECUTOR...",
        "💰 OPTIMIZADOR..."
    ]

    for p in pasos:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=p)
        await asyncio.sleep(0.2)

    workflow = generar_workflow_base()
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

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🚀 Workflow listo (mejorado)",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# 🎛 BOTONES
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    chat_id = query.message.chat.id

    if query.data == "ver":
        txt = json.dumps(estado.get(uid, {}), indent=2)
        await context.bot.send_message(chat_id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        await context.bot.send_message(chat_id, "🚀 Creando en n8n...")

        res = crear_workflow(estado.get(uid))

        await context.bot.send_message(chat_id, f"✅ Respuesta:\n{res}")

    elif query.data == "regen":
        await context.bot.send_message(chat_id, "🔄 Regenerando correctamente...")

        workflow = generar_workflow_base()
        estado[uid] = workflow

        await context.bot.send_message(chat_id, "✅ Workflow regenerado")

# 📩 MENSAJES
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)

# 🚀 BOT
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW PRO ACTIVO")
app.run_polling()
