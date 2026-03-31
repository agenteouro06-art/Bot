import os
import json
import time
import random
import requests
from uuid import uuid4
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
# 🧠 GENERADOR REAL PRO
# =========================

def generar_flujo_completo():

    def uid():
        return str(uuid4())

    return {
        "name": f"WhatsApp OCR Pago {random.randint(100,999)}",
        "nodes": [

            # 🔹 WEBHOOK (entrada desde WhatsApp / backend)
            {
                "id": uid(),
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200,300],
                "parameters": {
                    "path": "validar-transferencia",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },

            # 🔹 OCR API (ej: OCR.space / Google Vision)
            {
                "id": uid(),
                "name": "OCR",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [450,300],
                "parameters": {
                    "url": "https://api.ocr.space/parse/image",
                    "requestMethod": "POST",
                    "sendBinaryData": False,
                    "jsonParameters": True,
                    "options": {},
                    "bodyParametersJson": """{
                        "url": "={{$json.image_url}}",
                        "apikey": "TU_API_KEY_OCR"
                    }"""
                }
            },

            # 🔹 LIMPIAR TEXTO OCR
            {
                "id": uid(),
                "name": "Procesar OCR",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [700,300],
                "parameters": {
                    "functionCode": """
const texto = JSON.stringify($json);

return [{
  json: {
    texto: texto,
    referencia: $json.referencia || '',
    monto: $json.monto || ''
  }
}];
"""
                }
            },

            # 🔹 VALIDACIÓN BANCO (API REAL FUTURA)
            {
                "id": uid(),
                "name": "Validar Banco",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [950,300],
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

            # 🔹 LÓGICA DE VALIDACIÓN
            {
                "id": uid(),
                "name": "IF",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2,
                "position": [1200,300],
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

            # 🔹 RESPUESTA OK
            {
                "id": uid(),
                "name": "OK",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [1450,200],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "respuesta",
                                "value": "✅ Pago confirmado"
                            }
                        ]
                    }
                }
            },

            # 🔹 RESPUESTA FAIL
            {
                "id": uid(),
                "name": "FAIL",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [1450,400],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "respuesta",
                                "value": "❌ Pago no coincide"
                            }
                        ]
                    }
                }
            },

            # 🔹 RESPONDER WEBHOOK
            {
                "id": uid(),
                "name": "Responder",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [1700,300],
                "parameters": {
                    "responseCode": 200,
                    "responseData": "={{$json.respuesta}}"
                }
            }

        ],

        "connections": {
            "Webhook": {
                "main": [[{"node": "OCR", "type": "main", "index": 0}]]
            },
            "OCR": {
                "main": [[{"node": "Procesar OCR", "type": "main", "index": 0}]]
            },
            "Procesar OCR": {
                "main": [[{"node": "Validar Banco", "type": "main", "index": 0}]]
            },
            "Validar Banco": {
                "main": [[{"node": "IF", "type": "main", "index": 0}]]
            },
            "IF": {
                "main": [
                    [{"node": "OK", "type": "main", "index": 0}],
                    [{"node": "FAIL", "type": "main", "index": 0}]
                ]
            },
            "OK": {
                "main": [[{"node": "Responder", "type": "main", "index": 0}]]
            },
            "FAIL": {
                "main": [[{"node": "Responder", "type": "main", "index": 0}]]
            }
        },

        "settings": {}
    }

# =========================
# 🧼 LIMPIADOR
# =========================

def limpiar(wf):
    for k in ["id","active","versionId","meta","pinData","createdAt","updatedAt","triggerCount"]:
        wf.pop(k, None)
    wf["settings"] = {}
    return wf

# =========================
# 🚀 CREAR EN N8N
# =========================

def crear_n8n(wf):

    for i in range(3):

        wf = limpiar(wf)

        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=wf
        )

        if r.status_code in [200,201]:
            return r.json()

        wf = generar_flujo_completo()
        time.sleep(1)

    return {"error": "fallo total"}

# =========================
# 🤖 BOT
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ALLOWED_USER:
        return

    wf = generar_flujo_completo()
    estado[update.effective_user.id] = wf

    kb = [
        [InlineKeyboardButton("🚀 Crear", callback_data="crear")],
        [InlineKeyboardButton("📄 Ver JSON", callback_data="ver")]
    ]

    await update.message.reply_text("🔥 Flujo PRO generado", reply_markup=InlineKeyboardMarkup(kb))

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if q.data == "ver":
        await context.bot.send_message(q.message.chat.id, json.dumps(estado[uid], indent=2))

    if q.data == "crear":
        res = crear_n8n(estado[uid])
        await context.bot.send_message(q.message.chat.id, str(res))

# =========================
# 🚀 START
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 SISTEMA SaaS OCR + WHATSAPP ACTIVO")
app.run_polling()
