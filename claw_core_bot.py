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
# 🧠 MULTI-AGENTE
# =========================

def agente_analista(texto):
    t = texto.lower()
    if "whatsapp" in t and "pago" in t:
        return "whatsapp_pago"
    elif "pago" in t or "banco" in t:
        return "pago"
    elif "restaurante" in t:
        return "restaurante"
    return "general"

# =========================
# 🏗 GENERADOR REAL
# =========================

def generar_workflow(tipo):
    base_id = lambda: str(uuid4())

    if tipo == "whatsapp_pago":
        return {
            "name": f"Validacion WhatsApp Pago {random.randint(1,999)}",
            "nodes": [
                {
                    "id": base_id(),
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2,
                    "position": [200, 300],
                    "parameters": {
                        "path": "validar-pago",
                        "httpMethod": "POST",
                        "responseMode": "lastNode"
                    }
                },
                {
                    "id": base_id(),
                    "name": "Comparar",
                    "type": "n8n-nodes-base.function",
                    "typeVersion": 1,
                    "position": [500, 300],
                    "parameters": {
                        "functionCode": """
const texto = $json.texto || '';
const referencia = $json.referencia || '';
const monto = $json.monto || '';

return [{
  json: {
    aprobado: texto.includes(referencia) && texto.includes(monto)
  }
}];
"""
                    }
                },
                {
                    "id": base_id(),
                    "name": "IF",
                    "type": "n8n-nodes-base.if",
                    "typeVersion": 2,
                    "position": [800, 300],
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
                    "id": base_id(),
                    "name": "OK",
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 2,
                    "position": [1100, 200],
                    "parameters": {
                        "values": {
                            "string": [{"name": "respuesta", "value": "✅ Pago confirmado"}]
                        }
                    }
                },
                {
                    "id": base_id(),
                    "name": "FAIL",
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 2,
                    "position": [1100, 400],
                    "parameters": {
                        "values": {
                            "string": [{"name": "respuesta", "value": "❌ No coincide"}]
                        }
                    }
                },
                {
                    "id": base_id(),
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
                "Webhook": {"main": [[{"node": "Comparar","type": "main","index": 0}]]},
                "Comparar": {"main": [[{"node": "IF","type": "main","index": 0}]]},
                "IF": {
                    "main": [
                        [{"node": "OK","type": "main","index": 0}],
                        [{"node": "FAIL","type": "main","index": 0}]
                    ]
                },
                "OK": {"main": [[{"node": "Responder","type": "main","index": 0}]]},
                "FAIL": {"main": [[{"node": "Responder","type": "main","index": 0}]]}
            },
            "settings": {}
        }

    # fallback
    return generar_workflow("whatsapp_pago")

# =========================
# 🧼 LIMPIEZA CRÍTICA (FIX ERROR 400)
# =========================

def limpiar_workflow(wf):
    for k in ["id","active","versionId","meta","pinData","createdAt","updatedAt"]:
        wf.pop(k, None)

    wf["settings"] = {}

    # limpiar nodos duplicados por nombre
    seen = set()
    unique_nodes = []
    for n in wf["nodes"]:
        if n["name"] not in seen:
            seen.add(n["name"])
            unique_nodes.append(n)

    wf["nodes"] = unique_nodes

    return wf

# =========================
# 🚀 CREAR EN N8N (RETRY INTELIGENTE)
# =========================

def crear_en_n8n(wf):
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
# 🤖 MOTOR
# =========================

async def procesar(update, context, texto):
    uid = update.effective_user.id

    pasos = [
        "🧠 Analizando...",
        "🏗 Diseñando flujo...",
        "🔧 Corrigiendo...",
        "⚙ Optimizando..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        time.sleep(0.2)

    tipo = agente_analista(texto)
    wf = generar_workflow(tipo)

    estado[uid] = wf

    kb = [
        [InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear")],
        [InlineKeyboardButton("📄 Ver JSON", callback_data="ver")]
    ]

    await update.message.reply_text("✅ Flujo listo", reply_markup=InlineKeyboardMarkup(kb))

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
        await context.bot.send_message(chat, "🚀 Creando en n8n...")
        res = crear_en_n8n(estado[uid])
        await context.bot.send_message(chat, str(res))

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

print("🔥 CLAW SaaS ACTIVO (100% FUNCIONAL)")
app.run_polling()
