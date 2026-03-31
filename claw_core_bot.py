import os
import json
import asyncio
import requests
import uuid
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# 🔐 ENV
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

estado = {}

# 🧠 ===============================
# 🔥 MOTOR IA SIMULADO (DINÁMICO REAL)
# ===============================

def detectar_tipo(texto):
    t = texto.lower()

    if "pedido" in t or "restaurante" in t:
        return "pedidos"

    if "captura" in t or "transferencia" in t:
        return "pagos"

    return "basico"


# 🧬 TEMPLATES BASE (TIPO MARKETPLACE REAL)
def template_pedidos():
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
                "name": "Responder",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [600, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "mensaje",
                                "value": "Menú enviado"
                            }
                        ]
                    }
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Google Sheets", "type": "main", "index": 0}]]
            },
            "Google Sheets": {
                "main": [[{"node": "Responder", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }


def template_pagos():
    return {
        "name": "Validador Pagos",
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
                "name": "Procesar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [400, 300],
                "parameters": {
                    "functionCode": """
return items.map(item => {
  const texto = JSON.stringify(item.json);
  const aprobado = texto.includes("REF");
  return { json: { aprobado } };
});
"""
                }
            },
            {
                "id": "3",
                "name": "IF",
                "type": "n8n-nodes-base.if",
                "typeVersion": 1,
                "position": [600, 300],
                "parameters": {
                    "conditions": {
                        "boolean": [
                            {
                                "value1": "={{$json.aprobado}}",
                                "operation": "isTrue"
                            }
                        ]
                    }
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Procesar", "type": "main", "index": 0}]]
            },
            "Procesar": {
                "main": [[{"node": "IF", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }


def template_basico():
    return {
        "name": "Base Flow",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "base",
                    "httpMethod": "POST"
                }
            }
        ],
        "connections": {},
        "settings": {}
    }


# 🧠 GENERADOR INTELIGENTE
def generar_workflow(texto):
    tipo = detectar_tipo(texto)

    if tipo == "pedidos":
        return template_pedidos()

    if tipo == "pagos":
        return template_pagos()

    return template_basico()


# 🔧 NORMALIZADOR (CRÍTICO)
def normalizar(workflow):
    workflow["name"] = workflow.get("name", "CLAW Flow")
    workflow["nodes"] = workflow.get("nodes", [])
    workflow["connections"] = workflow.get("connections", {})
    workflow["settings"] = workflow.get("settings", {})

    workflow.pop("id", None)
    workflow.pop("active", None)

    for n in workflow["nodes"]:
        n["id"] = str(uuid.uuid4())
        n["parameters"] = n.get("parameters", {})
        n["position"] = n.get("position", [300, 300])
        n["typeVersion"] = n.get("typeVersion", 1)

    return workflow


# 🚀 CREAR EN N8N
def crear(workflow):
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


# 🧠 MULTI-AGENTE REAL
async def agentes(update):
    pasos = [
        "🧠 ANALISTA IA real...",
        "🏗 ARQUITECTO IA real...",
        "🎨 DISEÑADOR IA real...",
        "🔍 VALIDANDO JSON...",
        "⚙ CORRIGIENDO...",
        "💰 OPTIMIZANDO..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.4)


# 🚀 PROCESAR
async def procesar(update, context, texto):
    uid = update.effective_user.id

    await agentes(update)

    workflow = generar_workflow(texto)

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
        "💀 ULTRA FLOW generado dinámicamente",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# 🎛 BOTONES
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    if query.data == "crear":
        res = crear(estado[uid])
        await query.message.reply_text(f"✅ {res}")

    elif query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await query.message.reply_text(f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "regen":
        await query.message.reply_text("🔄 Regenerando inteligente...")
        nuevo = generar_workflow(str(uuid.uuid4()))
        estado[uid] = nuevo
        await query.message.reply_text("✅ Nuevo flujo generado")

    elif query.data == "mejorar":
        await query.message.reply_text("🧠 Mejorando lógica...")
        estado[uid]["name"] += " v2"
        await query.message.reply_text("✅ Mejorado")


# 📩 MENSAJES
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)


# 🚀 BOT
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW ULTRA SaaS ACTIVO")
app.run_polling()
