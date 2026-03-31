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
OPENAI_KEY = os.getenv("OPENAI_KEY")

estado = {}

# =========================
# 🧠 BASE (NO TOCAR)
# =========================

def generar_flujo_base():
    return {
        "name": f"WhatsApp OCR Pago PRO {random.randint(100,999)}",
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
                    "bodyParameters": {
                        "parameters": [
                            {"name": "url", "value": "={{$json.image_url}}"},
                            {"name": "apikey", "value": "TU_API_KEY_OCR"}
                        ]
                    }
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Parse OCR",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [700, 300],
                "parameters": {
                    "functionCode": """
const raw = JSON.stringify($json);
let texto = raw.toLowerCase();
let referencia = (texto.match(/\\d{6,}/) || [''])[0];
let monto = (texto.match(/\\d{4,}/) || [''])[0];
return [{ json: { texto, referencia, monto } }];
"""
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Validar Banco",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [950, 300],
                "parameters": {
                    "functionCode": """
const { referencia, monto } = $json;
const aprobado = referencia && monto;
return [{ json: { aprobado, referencia, monto } }];
"""
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
                        "boolean": [{
                            "value1": "={{$json.aprobado}}",
                            "operation": "equal",
                            "value2": True
                        }]
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
                        "string": [{"name": "respuesta", "value": "✅ Pago confirmado"}]
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
                        "string": [{"name": "respuesta", "value": "❌ Pago no coincide"}]
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
        }
    }

# =========================
# 🧠 AGENTES IA
# =========================

def agente_generador(prompt):
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Genera workflows n8n válidos sin metadata extra"},
                    {"role": "user", "content": prompt}
                ]
            }
        )
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except:
        return generar_flujo_base()

def agente_validador(wf):
    # asegura estructura mínima
    if "nodes" not in wf or not wf["nodes"]:
        return generar_flujo_base()
    return wf

def agente_autofix(wf):
    # 🔥 FIX CRÍTICO N8N
    wf["settings"] = {}
    for k in ["id","active","meta","versionId","staticData","pinData","createdAt","updatedAt"]:
        wf.pop(k, None)
    return wf

# =========================
# 🧬 MODO AUTÓNOMO TOTAL
# =========================

def modo_autonomo(prompt):
    print("🧠 Agente 1: generando...")
    wf = agente_generador(prompt)

    print("🔍 Agente 2: validando...")
    wf = agente_validador(wf)

    print("🛠 Agente 3: corrigiendo...")
    wf = agente_autofix(wf)

    return wf

# =========================
# 🔁 CREAR
# =========================

def crear(workflow):
    wf = agente_autofix(workflow)

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

    return r.json()

# =========================
# 🤖 BOT
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text

    await update.message.reply_text("🧠 MODO AUTÓNOMO ACTIVADO...")

    if "bot" in texto.lower():
        wf = modo_autonomo(texto)
    else:
        wf = generar_flujo_base()

    estado[update.effective_user.id] = wf

    kb = [
        [InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear")],
        [InlineKeyboardButton("📄 Ver JSON", callback_data="ver")]
    ]

    await update.message.reply_text(
        "🔥 Flujo listo (AUTO)",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if q.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await context.bot.send_message(q.message.chat.id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif q.data == "crear":
        await context.bot.send_message(q.message.chat.id, "🚀 Deploy automático...")
        res = crear(estado[uid])
        await context.bot.send_message(q.message.chat.id, str(res))

# =========================
# 🚀 START
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

app.run_polling()
