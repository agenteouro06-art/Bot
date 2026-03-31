import os
import json
import time
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
ALLOWED_USER = int(os.getenv("ALLOWED_USER", "0"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

estado = {}

# =========================
# 🧠 MULTI AGENTE
# =========================

def agente_analista(texto):
    t = texto.lower()

    if "whatsapp" in t and "pago" in t:
        return "whatsapp_pago"

    if "pago" in t or "banco" in t:
        return "validacion_pago"

    if "restaurante" in t:
        return "restaurante"

    return "basico"


# =========================
# 🏗 CONSTRUCTORES REALES
# =========================

def flujo_validacion_pago():
    return {
        "name": f"Validacion Pago {uuid.uuid4().hex[:4]}",
        "nodes": [
            {
                "id": "1",
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
                "id": "2",
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
                "id": "3",
                "name": "IF",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2,
                "position": [800, 300],
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
                "id": "4",
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
                "id": "5",
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
                "id": "6",
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
        "settings": {}
    }


def flujo_whatsapp_pago():
    wf = flujo_validacion_pago()
    wf["name"] = "WhatsApp Transfer Verify"

    return wf


def construir_flujo(tipo):
    if tipo == "whatsapp_pago":
        return flujo_whatsapp_pago()

    if tipo == "validacion_pago":
        return flujo_validacion_pago()

    return flujo_validacion_pago()


# =========================
# 🔧 NORMALIZADOR PRO
# =========================

def limpiar_workflow(wf):
    # eliminar basura n8n
    for k in ["id", "active", "versionId", "meta", "pinData", "createdAt", "updatedAt"]:
        wf.pop(k, None)

    wf["settings"] = {}

    ids = set()
    for i, n in enumerate(wf.get("nodes", []), start=1):
        n["id"] = str(i)

        # evitar duplicados
        if n["name"] in ids:
            n["name"] += f"_{i}"
        ids.add(n["name"])

        n["parameters"] = n.get("parameters", {})
        n["position"] = n.get("position", [200 + i * 250, 300])
        n["typeVersion"] = n.get("typeVersion", 1)

    return wf


# =========================
# 🚀 CREAR EN N8N CON RETRY
# =========================

def crear_en_n8n(wf):
    wf = limpiar_workflow(wf)

    for intento in range(3):
        print(f"🚀 Intento {intento+1}")

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
# 🤖 BOT TELEGRAM
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text

    await update.message.reply_text("🧠 Analizando...")
    tipo = agente_analista(texto)

    await update.message.reply_text("🏗 Construyendo flujo...")
    wf = construir_flujo(tipo)

    estado[update.effective_user.id] = wf

    kb = [
        [InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear")],
        [InlineKeyboardButton("📄 Ver JSON", callback_data="ver")]
    ]

    await update.message.reply_text(
        f"🔥 Flujo listo: {wf['name']}\n\n"
        f"👉 Tipo: {tipo}\n\n"
        f"⚠️ Falta configurar:\n"
        f"- Credenciales (WhatsApp API, Banco, etc)\n"
        f"- Endpoint webhook\n",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# =========================
# 🎛 BOTONES
# =========================

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    wf = estado.get(uid)

    if not wf:
        await context.bot.send_message(query.message.chat.id, "No hay flujo.")
        return

    if query.data == "ver":
        txt = json.dumps(wf, indent=2)
        await context.bot.send_message(query.message.chat.id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        await context.bot.send_message(query.message.chat.id, "🚀 Creando en n8n...")
        res = crear_en_n8n(wf)
        await context.bot.send_message(query.message.chat.id, str(res))


# =========================
# 🚀 START
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW GOD MODE SaaS ACTIVO")
app.run_polling()
