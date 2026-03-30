import os
import json
import asyncio
import requests
import copy
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# 🔥 ENV (NO TOCAR)
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

estado = {}

# 🔥 WORKFLOW REAL BASE (MODO DIOS)
def generar_workflow_dios():
    return {
        "name": "CLAW GOD FLOW - WhatsApp Validator",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook WhatsApp",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "whatsapp-in",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },
            {
                "id": "2",
                "name": "Set Datos Entrada",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [400, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "imagen_url", "value": "={{$json.body.image}}"},
                            {"name": "mensaje_id", "value": "={{$json.body.id}}"}
                        ]
                    }
                }
            },
            {
                "id": "3",
                "name": "HTTP Descargar Imagen",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 2,
                "position": [600, 300],
                "parameters": {
                    "url": "={{$json.imagen_url}}",
                    "responseFormat": "file"
                }
            },
            {
                "id": "4",
                "name": "OCR Placeholder",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [800, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "texto_extraido",
                                "value": "REF12345 MONTO 50000"
                            }
                        ]
                    }
                }
            },
            {
                "id": "5",
                "name": "Email Banco (Mock)",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [1000, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "referencia_banco",
                                "value": "REF12345"
                            },
                            {
                                "name": "monto_banco",
                                "value": "50000"
                            }
                        ]
                    }
                }
            },
            {
                "id": "6",
                "name": "Function Comparar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [1200, 300],
                "parameters": {
                    "functionCode": """
const texto = $json.texto_extraido;
const refBanco = $json.referencia_banco;
const montoBanco = $json.monto_banco;

const coincideRef = texto.includes(refBanco);
const coincideMonto = texto.includes(montoBanco);

return [{
  json: {
    aprobado: coincideRef && coincideMonto
  }
}];
"""
                }
            },
            {
                "id": "7",
                "name": "IF Aprobado",
                "type": "n8n-nodes-base.if",
                "typeVersion": 1,
                "position": [1400, 300],
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
            },
            {
                "id": "8",
                "name": "Set Respuesta OK",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [1600, 200],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "respuesta", "value": "✅ Pago validado"}
                        ]
                    }
                }
            },
            {
                "id": "9",
                "name": "Set Respuesta FAIL",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [1600, 400],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "respuesta", "value": "❌ No coincide"}
                        ]
                    }
                }
            }
        ],
        "connections": {
            "Webhook WhatsApp": {
                "main": [[{"node": "Set Datos Entrada", "type": "main", "index": 0}]]
            },
            "Set Datos Entrada": {
                "main": [[{"node": "HTTP Descargar Imagen", "type": "main", "index": 0}]]
            },
            "HTTP Descargar Imagen": {
                "main": [[{"node": "OCR Placeholder", "type": "main", "index": 0}]]
            },
            "OCR Placeholder": {
                "main": [[{"node": "Email Banco (Mock)", "type": "main", "index": 0}]]
            },
            "Email Banco (Mock)": {
                "main": [[{"node": "Function Comparar", "type": "main", "index": 0}]]
            },
            "Function Comparar": {
                "main": [[{"node": "IF Aprobado", "type": "main", "index": 0}]]
            },
            "IF Aprobado": {
                "main": [
                    [{"node": "Set Respuesta OK", "type": "main", "index": 0}],
                    [{"node": "Set Respuesta FAIL", "type": "main", "index": 0}]
                ]
            }
        },
        "settings": {}
    }

# 🔥 NORMALIZAR (NO TOCAR)
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

# 🔥 CREAR WORKFLOW (NO TOCAR)
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

    workflow = generar_workflow_dios()
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
        text="💀 CLAW GOD FLOW listo",
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
        await context.bot.send_message(chat_id, "🔄 Regenerando modo dios...")

        workflow = generar_workflow_dios()
        estado[uid] = workflow

        await context.bot.send_message(chat_id, "💀 Nuevo workflow listo")

# 📩 MENSAJES
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)

# 🚀 BOT
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW DIOS ACTIVO")
app.run_polling()
