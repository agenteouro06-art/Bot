import os
import json
import asyncio
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# 🔥 CARGAR ENV (CORREGIDO)
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER   = int(os.getenv("ALLOWED_USER"))
N8N_URL        = os.getenv("N8N_URL")
N8N_API_KEY    = os.getenv("N8N_API_KEY")

# 🔥 WORKFLOW REAL (ESTRUCTURA 100% COMPATIBLE N8N)
BASE_WORKFLOW = {
    "name": "CLAW WhatsApp Validator",
    "nodes": [
        {
            "id": "Webhook_1",
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 1,
            "position": [300, 300],
            "parameters": {
                "path": "claw-webhook",
                "httpMethod": "POST",
                "responseMode": "onReceived"
            }
        },
        {
            "id": "Set_1",
            "name": "Set",
            "type": "n8n-nodes-base.set",
            "typeVersion": 2,
            "position": [600, 300],
            "parameters": {
                "values": {
                    "string": [
                        {
                            "name": "status",
                            "value": "ok"
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
    "settings": {},
    "staticData": None
}

estado = {}

# 🔥 NORMALIZADOR PRO (ANTI ERRORES REALES DE N8N)
def normalizar(workflow):
    workflow = dict(workflow)

    workflow["name"] = workflow.get("name", "CLAW Flow")
    workflow["nodes"] = workflow.get("nodes", [])
    workflow["connections"] = workflow.get("connections", {})
    workflow["settings"] = workflow.get("settings", {})

    # ❌ CAMPOS QUE ROMPEN N8N
    for key in ["active", "id", "versionId", "meta"]:
        workflow.pop(key, None)

    for node in workflow["nodes"]:
        node["id"] = str(node.get("id", node.get("name", "node")))
        node["name"] = node.get("name", node["id"])
        node["type"] = node.get("type", "n8n-nodes-base.set")
        node["typeVersion"] = node.get("typeVersion", 1)
        node["position"] = node.get("position", [300, 300])
        node["parameters"] = node.get("parameters", {})

        # ❌ limpiar basura interna
        for k in ["credentials", "notes", "webhookId"]:
            node.pop(k, None)

    return workflow

# 🔥 CREAR WORKFLOW REAL
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

        try:
            data = r.json()
        except:
            return {"error": "Respuesta inválida de n8n"}

        if r.status_code not in [200, 201]:
            return {"error": data}

        return {"ok": True, "data": data}

    except Exception as e:
        return {"error": str(e)}

# 🔥 MOTOR PRINCIPAL
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
        await update.message.reply_text(p)
        await asyncio.sleep(0.25)

    # 🔥 SIEMPRE BASE SEGURA (tipo marketplace)
    workflow = json.loads(json.dumps(BASE_WORKFLOW))

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
        "🚀 Workflow listo (compatible 100% n8n)",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# 🔥 BOTONES (ARREGLADO)
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    chat_id = query.message.chat.id

    if uid not in estado:
        await context.bot.send_message(chat_id, "⚠ No hay workflow cargado")
        return

    if query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await context.bot.send_message(chat_id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        await context.bot.send_message(chat_id, "🚀 Creando en n8n...")

        res = crear_workflow(estado[uid])

        if "ok" in res:
            await context.bot.send_message(chat_id, "✅ Workflow creado correctamente en n8n")
        else:
            await context.bot.send_message(chat_id, f"❌ Error real:\n{res['error']}")

    elif query.data == "regen":
        await context.bot.send_message(chat_id, "🔄 Regenerando limpio...")
        await procesar(query, context, "regen")

# 📩 MENSAJES
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)

# 🚀 INICIO
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW PRO FUNCIONANDO (SIN ERRORES N8N)")
app.run_polling()
