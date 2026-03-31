import os
import json
import uuid
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, CallbackQueryHandler, filters

# =========================
# 🔥 ENV
# =========================

load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER   = int(os.getenv("ALLOWED_USER"))
N8N_URL        = os.getenv("N8N_URL")
N8N_API_KEY    = os.getenv("N8N_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

print("🔥 BOT ACTIVO (GIFHUD READY)")

estado = {}

# =========================
# 🧠 OPENROUTER FIX
# =========================

def llamar_ia(prompt):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-3-haiku",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000
            },
            timeout=20
        )

        data = r.json()

        if "error" in data:
            print("❌ ERROR IA:", data)
            return None

        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print("❌ ERROR IA:", e)
        return None

# =========================
# 🧬 FLUJO REAL (SIEMPRE FUNCIONA)
# =========================

def flujo_real():
    return {
        "name": "Validación transferencia OCR + Email",
        "settings": {},

        "nodes": [
            {
                "id": str(uuid.uuid4()),
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
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
                "typeVersion": 1,
                "position": [400, 300],
                "parameters": {
                    "url": "https://api.ocr.space/parse/image",
                    "method": "POST",
                    "jsonParameters": True,
                    "bodyParametersJson": """
                    {
                        "url": "{{$json.image_url}}",
                        "apikey": "TU_API_KEY_OCR"
                    }
                    """
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Parse OCR",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [600, 300],
                "parameters": {
                    "functionCode": """
const texto = JSON.stringify($json).toLowerCase();
const referencia = (texto.match(/\\d{6,}/) || [''])[0];
const monto = (texto.match(/\\d{4,}/) || [''])[0];
return [{ json: { referencia, monto } }];
"""
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Comparar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [800, 300],
                "parameters": {
                    "functionCode": """
const aprobado = $json.referencia && $json.monto;
return [{ json: { aprobado } }];
"""
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "IF",
                "type": "n8n-nodes-base.if",
                "typeVersion": 1,
                "position": [1000, 300],
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
                "typeVersion": 1,
                "position": [1200, 200],
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
                "typeVersion": 1,
                "position": [1200, 400],
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
                "position": [1400, 300],
                "parameters": {
                    "responseCode": 200,
                    "responseData": "={{$json.respuesta}}"
                }
            }
        ],

        "connections": {
            "Webhook": {"main": [[{"node": "OCR", "type": "main", "index": 0}]]},
            "OCR": {"main": [[{"node": "Parse OCR", "type": "main", "index": 0}]]},
            "Parse OCR": {"main": [[{"node": "Comparar", "type": "main", "index": 0}]]},
            "Comparar": {"main": [[{"node": "IF", "type": "main", "index": 0}]]},
            "IF": {
                "main": [
                    [{"node": "OK", "type": "main", "index": 0}],
                    [{"node": "FAIL", "type": "main", "index": 0}]
                ]
            },
            "OK": {"main": [[{"node": "Responder", "type": "main", "index": 0}]]},
            "FAIL": {"main": [[{"node": "Responder", "type": "main", "index": 0}]]}
        }
    }

# =========================
# 🔧 LIMPIEZA FINAL (FIX N8N)
# =========================

def limpiar(workflow):
    workflow = dict(workflow)
    workflow["settings"] = {}

    # 🔥 SOLO dejar campos válidos
    return {
        "name": workflow.get("name", "Flujo"),
        "nodes": workflow.get("nodes", []),
        "connections": workflow.get("connections", {}),
        "settings": {}
    }

# =========================
# 🚀 CREAR EN N8N
# =========================

def crear_flujo():
    flujo = limpiar(flujo_real())

    r = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        headers={
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json"
        },
        json=flujo
    )

    print("STATUS:", r.status_code)
    print("RESP:", r.text[:500])

    try:
        return r.json()
    except:
        return {}

# =========================
# 🤖 TELEGRAM
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return
    await update.message.reply_text("🔥 CLAW CORE ACTIVO\n\nEscribe:\ncrear flujo")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text.lower()

    if "flujo" in texto:
        await update.message.reply_text("🧠 Creando flujo...")
        res = crear_flujo()

        if res.get("id"):
            await update.message.reply_text(f"✅ Flujo creado\nID: {res['id']}")
        else:
            await update.message.reply_text(f"❌ Error:\n{res}")

# =========================
# 🚀 START BOT
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, handle))

app.run_polling()
