import os
import json
import uuid
import time
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
# 🧠 GENERADOR REAL INTELIGENTE
# =========================

def generar_flujo_avanzado(texto):
    return {
        "name": f"WhatsApp OCR Pago {random.randint(100,999)}",
        "nodes": [
            {
                "id": str(uuid.uuid4()),
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "validar-transferencia",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "OCR",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [450, 300],
                "parameters": {
                    "url": "https://api.ocr.space/parse/image",
                    "requestMethod": "POST",
                    "jsonParameters": True,
                    "bodyParametersJson": """{
"apikey": "TU_API_KEY_OCR",
"url": "={{$json.image_url}}"
}"""
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Procesar OCR",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [700, 300],
                "parameters": {
                    "functionCode": """
const texto = JSON.stringify($json);

return [{
  json: {
    texto,
    referencia: $json.referencia || '',
    monto: $json.monto || ''
  }
}];
"""
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Validar Banco",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [950, 300],
                "parameters": {
                    "url": "https://api.tubanco.com/validar",
                    "requestMethod": "POST",
                    "jsonParameters": True,
                    "bodyParametersJson": """{
"referencia": "={{$json.referencia}}",
"monto": "={{$json.monto}}"
}"""
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "IF",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2,
                "position": [1200, 300],
                "parameters": {
                    "conditions": {
                        "boolean": [
                            {
                                "value1": "={{$json.aprobado}}",
                                "operation": "equal",
                                "value2": True
                            }
                        ]
                    }
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "OK",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [1450, 200],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "respuesta", "value": "✅ Pago confirmado"}
                        ]
                    }
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "FAIL",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [1450, 400],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "respuesta", "value": "❌ Pago no coincide"}
                        ]
                    }
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Responder",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [1700, 300],
                "parameters": {
                    "responseCode": 200,
                    "responseData": "={{$json.respuesta}}"
                }
            }
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "OCR","type": "main","index": 0}]]},
            "OCR": {"main": [[{"node": "Procesar OCR","type": "main","index": 0}]]},
            "Procesar OCR": {"main": [[{"node": "Validar Banco","type": "main","index": 0}]]},
            "Validar Banco": {"main": [[{"node": "IF","type": "main","index": 0}]]},
            "IF": {
                "main": [
                    [{"node": "OK","type": "main","index": 0}],
                    [{"node": "FAIL","type": "main","index": 0}]
                ]
            },
            "OK": {"main": [[{"node": "Responder","type": "main","index": 0}]]},
            "FAIL": {"main": [[{"node": "Responder","type": "main","index": 0}]]}
        }
    }

# =========================
# 🔥 NORMALIZADOR PERFECTO
# =========================

def normalizar(workflow):
    workflow.pop("id", None)
    workflow.pop("active", None)
    workflow.pop("versionId", None)
    workflow.pop("createdAt", None)
    workflow.pop("updatedAt", None)
    workflow.pop("meta", None)
    workflow.pop("pinData", None)
    workflow.pop("staticData", None)

    # ⚠️ CLAVE DEL BUG
    workflow["settings"] = {
        "executionOrder": "v1"
    }

    workflow["connections"] = workflow.get("connections", {})
    workflow["nodes"] = workflow.get("nodes", [])

    # eliminar nodos duplicados por nombre
    names = set()
    clean_nodes = []
    for n in workflow["nodes"]:
        if n["name"] not in names:
            names.add(n["name"])
            clean_nodes.append(n)
    workflow["nodes"] = clean_nodes

    return workflow

# =========================
# 🚀 CREAR CON RETRY REAL
# =========================

def crear_con_retry(workflow):
    for i in range(3):
        print(f"🚀 Intento {i+1}")
        wf = normalizar(workflow)

        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=wf
        )

        print("STATUS:", r.status_code)
        print("RESP:", r.text)

        if r.status_code in [200, 201]:
            return r.json()

        time.sleep(1)

    return {"error": "❌ Falló después de 3 intentos"}

# =========================
# 🤖 BOT
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text

    await update.message.reply_text("🧠 Generando flujo PRO...")

    wf = generar_flujo_avanzado(texto)
    estado[update.effective_user.id] = wf

    kb = [
        [InlineKeyboardButton("🚀 Crear", callback_data="crear")],
        [InlineKeyboardButton("📄 JSON", callback_data="json")]
    ]

    await update.message.reply_text("💀 Flujo listo", reply_markup=InlineKeyboardMarkup(kb))

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    wf = estado.get(uid)

    if query.data == "json":
        txt = json.dumps(wf, indent=2)
        await context.bot.send_message(query.message.chat.id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        await context.bot.send_message(query.message.chat.id, "🚀 Creando en n8n...")
        res = crear_con_retry(wf)
        await context.bot.send_message(query.message.chat.id, str(res))

# =========================
# 🚀 START
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW GOD MODE SaaS ACTIVO")
app.run_polling()
