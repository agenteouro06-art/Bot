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
# 🔐 ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

estado = {}

# =========================
# 🧠 GENERADOR REAL (NUNCA VACÍO)
# =========================

def generar_flujo_inteligente(texto):

    # 🔥 DETECCIÓN AUTOMÁTICA
    texto = texto.lower()

    if "whatsapp" in texto or "ocr" in texto or "transferencia" in texto:
        return flujo_ocr_whatsapp()

    elif "restaurante" in texto:
        return flujo_restaurante()

    elif "pago" in texto:
        return flujo_validacion_pago()

    return flujo_base()

# =========================
# 🧩 FLUJOS REALES
# =========================

def flujo_ocr_whatsapp():
    return {
        "name": f"WhatsApp OCR Pago {random.randint(100,999)}",
        "nodes": [
            nodo_webhook(),
            nodo_http_ocr(),
            nodo_procesar_ocr(),
            nodo_validar_banco(),
            nodo_if(),
            nodo_ok(),
            nodo_fail(),
            nodo_responder()
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "OCR", "type": "main", "index": 0}]]},
            "OCR": {"main": [[{"node": "Procesar OCR", "type": "main", "index": 0}]]},
            "Procesar OCR": {"main": [[{"node": "Validar Banco", "type": "main", "index": 0}]]},
            "Validar Banco": {"main": [[{"node": "IF", "type": "main", "index": 0}]]},
            "IF": {
                "main": [
                    [{"node": "OK", "type": "main", "index": 0}],
                    [{"node": "FAIL", "type": "main", "index": 0}]
                ]
            },
            "OK": {"main": [[{"node": "Responder", "type": "main", "index": 0}]]},
            "FAIL": {"main": [[{"node": "Responder", "type": "main", "index": 0}]]}
        },
        "settings": {"executionOrder": "v1"}
    }

def flujo_validacion_pago():
    return {
        "name": f"Validacion Pago {random.randint(100,999)}",
        "nodes": [
            nodo_webhook(),
            nodo_comparar(),
            nodo_if(),
            nodo_ok(),
            nodo_fail(),
            nodo_responder()
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Comparar", "type": "main", "index": 0}]]},
            "Comparar": {"main": [[{"node": "IF", "type": "main", "index": 0}]]},
            "IF": {
                "main": [
                    [{"node": "OK", "type": "main", "index": 0}],
                    [{"node": "FAIL", "type": "main", "index": 0}]
                ]
            },
            "OK": {"main": [[{"node": "Responder", "type": "main", "index": 0}]]},
            "FAIL": {"main": [[{"node": "Responder", "type": "main", "index": 0}]]}
        },
        "settings": {"executionOrder": "v1"}
    }

def flujo_restaurante():
    return {
        "name": f"Pedidos Restaurante {random.randint(100,999)}",
        "nodes": [
            nodo_webhook(),
            nodo_set("pedido", "={{$json.body}}"),
            nodo_responder()
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Set", "type": "main", "index": 0}]]},
            "Set": {"main": [[{"node": "Responder", "type": "main", "index": 0}]]}
        },
        "settings": {"executionOrder": "v1"}
    }

def flujo_base():
    return flujo_validacion_pago()

# =========================
# 🧱 NODOS
# =========================

def nodo_webhook():
    return {
        "id": str(uuid4()),
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [200, 300],
        "parameters": {
            "path": "entrada",
            "httpMethod": "POST",
            "responseMode": "lastNode"
        }
    }

def nodo_http_ocr():
    return {
        "id": str(uuid4()),
        "name": "OCR",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 3,
        "position": [450, 300],
        "parameters": {
            "url": "https://api.ocr.space/parse/image",
            "requestMethod": "POST",
            "jsonParameters": True,
            "bodyParametersJson": "{\"url\":\"={{$json.image_url}}\",\"apikey\":\"TU_API_KEY\"}"
        }
    }

def nodo_procesar_ocr():
    return {
        "id": str(uuid4()),
        "name": "Procesar OCR",
        "type": "n8n-nodes-base.function",
        "typeVersion": 1,
        "position": [700, 300],
        "parameters": {
            "functionCode": """
const texto = JSON.stringify($json);
return [{json:{texto, referencia:$json.referencia, monto:$json.monto}}];
"""
        }
    }

def nodo_validar_banco():
    return {
        "id": str(uuid4()),
        "name": "Validar Banco",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 3,
        "position": [950, 300],
        "parameters": {
            "url": "https://api.tubanco.com/validar",
            "requestMethod": "POST",
            "jsonParameters": True,
            "bodyParametersJson": "{\"referencia\":\"={{$json.referencia}}\",\"monto\":\"={{$json.monto}}\"}"
        }
    }

def nodo_comparar():
    return {
        "id": str(uuid4()),
        "name": "Comparar",
        "type": "n8n-nodes-base.function",
        "typeVersion": 1,
        "position": [500, 300],
        "parameters": {
            "functionCode": """
const texto = $json.texto || '';
const referencia = $json.referencia || '';
const monto = $json.monto || '';
return [{json:{aprobado: texto.includes(referencia) && texto.includes(monto)}}];
"""
        }
    }

def nodo_if():
    return {
        "id": str(uuid4()),
        "name": "IF",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [800, 300],
        "parameters": {
            "conditions": {
                "boolean": [
                    {"value1": "={{$json.aprobado}}", "operation": "equal", "value2": True}
                ]
            }
        }
    }

def nodo_ok():
    return nodo_set("respuesta", "✅ Pago confirmado", "OK", [1100,200])

def nodo_fail():
    return nodo_set("respuesta", "❌ Pago no coincide", "FAIL", [1100,400])

def nodo_set(nombre, valor, label="Set", pos=[1100,300]):
    return {
        "id": str(uuid4()),
        "name": label,
        "type": "n8n-nodes-base.set",
        "typeVersion": 2,
        "position": pos,
        "parameters": {
            "values": {
                "string": [{"name": nombre, "value": valor}]
            }
        }
    }

def nodo_responder():
    return {
        "id": str(uuid4()),
        "name": "Responder",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1,
        "position": [1400, 300],
        "parameters": {
            "responseCode": 200,
            "responseData": "={{$json.respuesta}}"
        }
    }

# =========================
# 🔥 API N8N (FIX REAL)
# =========================

def limpiar_workflow(wf):
    wf = dict(wf)

    wf.pop("id", None)
    wf.pop("active", None)
    wf.pop("versionId", None)
    wf.pop("meta", None)
    wf.pop("pinData", None)
    wf.pop("staticData", None)

    wf["settings"] = {"executionOrder": "v1"}

    return wf

def crear_n8n_retry(wf):
    wf = limpiar_workflow(wf)

    for i in range(3):
        print(f"🚀 Intento {i+1}")

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

    await update.message.reply_text("🧠 Generando flujo SaaS real...")

    wf = generar_flujo_inteligente(texto)

    estado[update.effective_user.id] = wf

    kb = [
        [InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear")],
        [InlineKeyboardButton("📄 Ver JSON", callback_data="ver")]
    ]

    await update.message.reply_text("🔥 Flujo listo", reply_markup=InlineKeyboardMarkup(kb))

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    wf = estado.get(uid)

    if query.data == "ver":
        txt = json.dumps(wf, indent=2)
        await context.bot.send_message(query.message.chat.id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        await context.bot.send_message(query.message.chat.id, "🚀 Creando en n8n...")
        res = crear_n8n_retry(wf)
        await context.bot.send_message(query.message.chat.id, str(res))

# =========================
# 🚀 RUN
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW GOD MODE SaaS ACTIVO")
app.run_polling()
