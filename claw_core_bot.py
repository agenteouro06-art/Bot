import os
import json
import asyncio
import random
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# =========================
# 🔥 ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

estado = {}

# =========================
# 🧠 TEMPLATES
# =========================

def template_restaurante():
    return {
        "name": "Pedidos Restaurante",
        "nodes": [
            {
                "id": "webhook_1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "pedido",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },
            {
                "id": "set_1",
                "name": "Set Pedido",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [500, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "pedido", "value": "={{$json.body}}"}
                        ]
                    }
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Set Pedido", "type": "main", "index": 0}]]
            }
        }
    }

def template_validacion_pago():
    return {
        "name": "Validacion Pago",
        "nodes": [
            {
                "id": "webhook_pago",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "pago",
                    "httpMethod": "POST"
                }
            },
            {
                "id": "func_1",
                "name": "Comparar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [500, 300],
                "parameters": {
                    "functionCode": """
const texto = $json.texto || '';
const banco = $json.banco || '';

return [{
  json: {
    aprobado: texto.includes(banco)
  }
}]
"""
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Comparar", "type": "main", "index": 0}]]
            }
        }
    }

# =========================
# 🧠 MULTI AGENTE
# =========================

def agente_analista(texto):
    t = texto.lower()
    if "restaurante" in t:
        return "restaurante"
    if "pago" in t or "banco" in t:
        return "pago"
    return "restaurante"

def agente_arquitecto(tipo):
    return template_restaurante() if tipo == "restaurante" else template_validacion_pago()

def agente_diseñador(wf):
    wf["name"] += f" v{random.randint(1,100)}"
    return wf

def agente_optimizador(wf):
    if random.random() > 0.5:
        wf["nodes"].append({
            "id": f"extra_{random.randint(100,999)}",
            "name": "Extra",
            "type": "n8n-nodes-base.set",
            "typeVersion": 2,
            "position": [800, 300],
            "parameters": {
                "values": {
                    "string": [{"name": "opt", "value": "ok"}]
                }
            }
        })
    return wf

# =========================
# 🔥 NORMALIZADOR PRO
# =========================

def normalizar(wf):
    wf["name"] = wf.get("name", "CLAW Flow")
    wf["nodes"] = wf.get("nodes", [])
    wf["connections"] = wf.get("connections", {})
    wf["settings"] = {"executionOrder": "v1"}
    wf["pinData"] = {}

    for i, node in enumerate(wf["nodes"]):
        node["id"] = node.get("id", f"node_{i}")
        node["parameters"] = node.get("parameters", {})
        node["position"] = node.get("position", [200 + i*250, 300])
        node["typeVersion"] = node.get("typeVersion", 1)

    return wf

# =========================
# 🚀 N8N API REAL
# =========================

def crear_workflow(wf):
    wf = normalizar(wf)

    r = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        headers={
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json"
        },
        json=wf,
        timeout=15
    )

    if r.status_code == 401:
        return {"error": "Unauthorized - API KEY mala"}

    try:
        return r.json()
    except:
        return {"error": r.text}

# =========================
# 🤖 MOTOR
# =========================

async def procesar(update, context, texto):
    uid = update.effective_user.id

    pasos = ["🧠 Analizando...", "🏗 Diseñando...", "⚙ Optimizando..."]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.3)

    tipo = agente_analista(texto)
    wf = agente_arquitecto(tipo)
    wf = agente_diseñador(wf)
    wf = agente_optimizador(wf)

    estado[uid] = wf

    kb = [
        [InlineKeyboardButton("🚀 Crear", callback_data="crear"),
         InlineKeyboardButton("📄 JSON", callback_data="ver")]
    ]

    await update.message.reply_text("🔥 Flow listo", reply_markup=InlineKeyboardMarkup(kb))

# =========================
# 🎛 BOTONES
# =========================

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    chat = q.message.chat.id

    if q.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await context.bot.send_message(chat, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif q.data == "crear":
        await context.bot.send_message(chat, "🚀 Enviando a n8n...")
        res = crear_workflow(estado[uid])
        await context.bot.send_message(chat, f"{res}")

# =========================
# 📩 MENSAJES
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return
    await procesar(update, context, update.message.text)

# =========================
# 🚀 START
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW PRO ACTIVO")
app.run_polling(drop_pending_updates=True)
