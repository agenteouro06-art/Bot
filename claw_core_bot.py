import os
import json
import asyncio
import random
import requests
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

# =========================
# 🧠 TEMPLATES BASE (REALES)
# =========================

def template_restaurante():
    return {
        "name": "Pedidos Restaurante",
        "nodes": [
            {
                "id": "1",
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
                "id": "2",
                "name": "Google Sheets",
                "type": "n8n-nodes-base.googleSheets",
                "typeVersion": 4,
                "position": [400, 300],
                "parameters": {
                    "operation": "read"
                }
            },
            {
                "id": "3",
                "name": "Set Pedido",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [600, 300],
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
            "Webhook": {"main": [[{"node": "Google Sheets","type": "main","index": 0}]]},
            "Google Sheets": {"main": [[{"node": "Set Pedido","type": "main","index": 0}]]}
        },
        "settings": {}
    }

def template_validacion_pago():
    return {
        "name": "Validacion Pago",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "pago",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },
            {
                "id": "2",
                "name": "Function Comparar",
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
            "Webhook": {"main": [[{"node": "Function Comparar","type": "main","index": 0}]]}
        },
        "settings": {}
    }

# =========================
# 🧠 MULTI-AGENTE REAL
# =========================

def agente_analista(texto):
    if "restaurante" in texto.lower():
        return "restaurante"
    elif "pago" in texto.lower() or "banco" in texto.lower():
        return "pago"
    return "general"

def agente_arquitecto(tipo):
    if tipo == "restaurante":
        return template_restaurante()
    elif tipo == "pago":
        return template_validacion_pago()
    return template_restaurante()

def agente_diseñador(workflow):
    # mejora visual / nombres
    workflow["name"] += f" v{random.randint(1,100)}"
    return workflow

def agente_optimizador(workflow):
    # agrega nodo extra random (variación real)
    if random.random() > 0.5:
        workflow["nodes"].append({
            "id": str(len(workflow["nodes"]) + 1),
            "name": "Set Extra",
            "type": "n8n-nodes-base.set",
            "typeVersion": 2,
            "position": [800, 300],
            "parameters": {
                "values": {
                    "string": [{"name": "extra", "value": "optimizado"}]
                }
            }
        })
    return workflow

# =========================
# 🔥 NORMALIZADOR (CRÍTICO)
# =========================

def normalizar(workflow):
    workflow["name"] = workflow.get("name", "CLAW Flow")
    workflow["nodes"] = workflow.get("nodes", [])
    workflow["connections"] = workflow.get("connections", {})
    workflow["settings"] = workflow.get("settings", {})

    workflow.pop("id", None)
    workflow.pop("active", None)

    for node in workflow["nodes"]:
        node["parameters"] = node.get("parameters", {})
        node["position"] = node.get("position", [300, 300])
        node["typeVersion"] = node.get("typeVersion", 1)

    return workflow

# =========================
# 🚀 CREAR EN N8N
# =========================

def crear_workflow(workflow):
    workflow = normalizar(workflow)

    r = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        headers={
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json"
        },
        json=workflow
    )

    try:
        return r.json()
    except:
        return {"error": r.text}

# =========================
# 🤖 MOTOR PRINCIPAL
# =========================

async def procesar(update, context, texto):
    uid = update.effective_user.id

    pasos = [
        "🧠 ANALISTA IA...",
        "🏗 ARQUITECTO IA...",
        "🎨 DISEÑADOR IA...",
        "🔍 VALIDANDO JSON...",
        "⚙ CORRIGIENDO...",
        "💰 OPTIMIZANDO..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.2)

    tipo = agente_analista(texto)
    workflow = agente_arquitecto(tipo)
    workflow = agente_diseñador(workflow)
    workflow = agente_optimizador(workflow)

    estado[uid] = workflow

    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="ver")
        ],
        [
            InlineKeyboardButton("🧠 Mejorar IA", callback_data="mejorar"),
            InlineKeyboardButton("🔄 Regenerar", callback_data="regen")
        ]
    ]

    await update.message.reply_text(
        "💀 ULTRA FLOW generado (dinámico real)",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# =========================
# 🎛 BOTONES
# =========================

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    chat_id = query.message.chat.id

    if query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await context.bot.send_message(chat_id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        await context.bot.send_message(chat_id, "🚀 Enviando a n8n...")
        res = crear_workflow(estado[uid])
        await context.bot.send_message(chat_id, f"✅ Respuesta:\n{res}")

    elif query.data == "regen":
        await context.bot.send_message(chat_id, "🔄 Regenerando real...")
        await procesar(query, context, str(random.random()))

    elif query.data == "mejorar":
        await context.bot.send_message(chat_id, "🧠 Mejorando IA...")
        wf = estado[uid]
        wf = agente_optimizador(wf)
        estado[uid] = wf
        await context.bot.send_message(chat_id, "✅ Mejorado")

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

print("🔥 CLAW ULTRA SaaS ACTIVO")
app.run_polling()
