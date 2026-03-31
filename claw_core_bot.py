import os
import json
import random
import uuid
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
# 🧠 GENERADOR BASE PRO
# =========================

def generar_flujo_completo():
    return {
        "name": f"WhatsApp OCR Pago PRO {random.randint(100,999)}",
        "nodes": [
            # 1. WEBHOOK
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

            # 2. OCR
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
                        "url": "={{$json.image_url}}",
                        "apikey": "TU_API_KEY_OCR"
                    }"""
                }
            },

            # 3. PROCESAR TEXTO
            {
                "id": str(uuid.uuid4()),
                "name": "Parse OCR",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [700, 300],
                "parameters": {
                    "functionCode": """
const raw = JSON.stringify($json);

// EXTRAER (simple heurístico)
let texto = raw.toLowerCase();
let referencia = (texto.match(/\\d{6,}/) || [''])[0];
let monto = (texto.match(/\\d{4,}/) || [''])[0];

return [{
  json: {
    texto,
    referencia,
    monto
  }
}];
"""
                }
            },

            # 4. VALIDACIÓN BANCO
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

            # 5. IF
            {
                "id": str(uuid.uuid4()),
                "name": "IF",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2,
                "position": [1200, 300],
                "parameters": {
                    "conditions": {
                        "boolean": [{
                            "value1": "={{$json.aprobado}}",
                            "operation": "equal",
                            "value2": True
                        }]
                    }
                }
            },

            # 6. OK
            {
                "id": str(uuid.uuid4()),
                "name": "OK",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [1450, 200],
                "parameters": {
                    "values": {
                        "string": [{"name": "respuesta", "value": "✅ Pago confirmado"}]
                    }
                }
            },

            # 7. FAIL
            {
                "id": str(uuid.uuid4()),
                "name": "FAIL",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [1450, 400],
                "parameters": {
                    "values": {
                        "string": [{"name": "respuesta", "value": "❌ Pago no coincide"}]
                    }
                }
            },

            # 8. RESPUESTA WEBHOOK
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
            "OCR": {"main": [[{"node": "Parse OCR","type": "main","index": 0}]]},
            "Parse OCR": {"main": [[{"node": "Validar Banco","type": "main","index": 0}]]},
            "Validar Banco": {"main": [[{"node": "IF","type": "main","index": 0}]]},
            "IF": {
                "main": [
                    [{"node": "OK","type": "main","index": 0}],
                    [{"node": "FAIL","type": "main","index": 0}]
                ]
            },
            "OK": {"main": [[{"node": "Responder","type": "main","index": 0}]]},
            "FAIL": {"main": [[{"node": "Responder","type": "main","index": 0}]]}
        },

        "settings": {}  # 🔥 FIX
    }

# =========================
# 🧠 GENERADOR DESDE TEXTO
# =========================

def generar_desde_texto(texto):
    texto = texto.lower()

    if "ocr" in texto or "whatsapp" in texto or "pago" in texto:
        return generar_flujo_completo()

    # fallback inteligente
    return generar_flujo_completo()

# =========================
# 🧠 CLONADOR MARKETPLACE
# =========================

def clonar_flujo_base():
    # simula clonado inteligente
    wf = generar_flujo_completo()
    wf["name"] += " CLONADO"
    return wf

# =========================
# 🧠 AUTO FIX
# =========================

def autofix(wf):
    nombres = [n["name"] for n in wf["nodes"]]

    if "Responder" not in nombres:
        wf = generar_flujo_completo()

    return wf

# =========================
# 🧹 LIMPIADOR
# =========================

def limpiar(workflow):
    for k in ["id","active","meta","versionId","staticData","pinData","createdAt","updatedAt"]:
        workflow.pop(k, None)

    workflow["settings"] = {}

    return workflow

# =========================
# 🧠 VALIDADOR
# =========================

def flujo_valido(wf):
    if not wf.get("nodes"):
        return False

    nombres = [n["name"] for n in wf["nodes"]]

    required = ["Webhook", "IF", "Responder"]

    return all(any(r in name for name in nombres) for r in required)

# =========================
# 🚀 CREAR CON RETRY
# =========================

def crear_con_retry(workflow):
    for intento in range(3):
        print(f"\n🚀 Intento {intento+1}")

        wf = limpiar(json.loads(json.dumps(workflow)))
        wf = autofix(wf)

        if not flujo_valido(wf):
            wf = generar_flujo_completo()

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

        if r.status_code in [200,201]:
            return r.json()

    return {"error": "❌ Falló después de 3 intentos"}

# =========================
# 🤖 BOT
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text

    wf = generar_desde_texto(texto)

    estado[update.effective_user.id] = wf

    kb = [
        [InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear")],
        [InlineKeyboardButton("📄 Ver JSON", callback_data="ver")]
    ]

    await update.message.reply_text("💀 Flujo SaaS generado", reply_markup=InlineKeyboardMarkup(kb))

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if q.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await context.bot.send_message(q.message.chat.id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif q.data == "crear":
        await context.bot.send_message(q.message.chat.id, "🚀 Creando en n8n...")
        res = crear_con_retry(estado[uid])
        await context.bot.send_message(q.message.chat.id, str(res))

# =========================
# 🚀 START
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 SaaS IA AUTOMATIZADO ACTIVO")
app.run_polling()
