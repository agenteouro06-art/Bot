import os
import json
import time
import uuid
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters
)

# =========================
# 🔐 ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER", "0"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

estado = {}

# =========================
# 🧠 ANALISTA
# =========================
def detectar_tipo(texto):
    t = texto.lower()
    if "pago" in t or "banco" in t:
        return "pago"
    if "restaurante" in t:
        return "restaurante"
    return "general"

# =========================
# 🏗 PLANTILLAS REALES
# =========================
def flujo_pago():
    return {
        "name": f"Validacion Pago {uuid.uuid4().hex[:4]}",
        "nodes": [
            {
                "id": str(uuid.uuid4()),
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "validar-pago",
                    "httpMethod": "POST"
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Comparar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [500, 300],
                "parameters": {
                    "functionCode": """
const texto = $json.texto || '';
const referencia = '123456';
const monto = '50000';

return [{
  json: {
    aprobado: texto.includes(referencia) && texto.includes(monto)
  }
}];
"""
                }
            },
            {
                "id": str(uuid.uuid4()),
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
                "id": str(uuid.uuid4()),
                "name": "OK",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [1100, 200],
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
                "position": [1100, 400],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "respuesta", "value": "❌ No coincide"}
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
        }
    }

# =========================
# 🧹 NORMALIZADOR PRO
# =========================
def limpiar_workflow(wf):
    # limpiar basura de n8n
    for k in ["id","active","versionId","meta","pinData","createdAt","updatedAt"]:
        wf.pop(k, None)

    wf["settings"] = {}  # 🔥 clave para evitar error

    # evitar duplicados por nombre
    nombres = set()
    nodos_limpios = []

    for n in wf.get("nodes", []):
        if n["name"] in nombres:
            continue
        nombres.add(n["name"])

        n["id"] = n.get("id", str(uuid.uuid4()))
        n["position"] = n.get("position", [300,300])
        n["parameters"] = n.get("parameters", {})
        n["typeVersion"] = n.get("typeVersion", 1)

        nodos_limpios.append(n)

    wf["nodes"] = nodos_limpios
    wf["connections"] = wf.get("connections", {})

    return wf

# =========================
# 🚀 CREAR EN N8N (RETRY)
# =========================
def crear_n8n(wf):
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
# 🧠 GENERADOR
# =========================
def generar(texto):
    tipo = detectar_tipo(texto)

    if tipo == "pago":
        return flujo_pago()

    return flujo_pago()

# =========================
# 🤖 MENSAJES
# =========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text

    await update.message.reply_text("🧠 Analizando...")
    wf = generar(texto)

    estado[update.effective_user.id] = wf

    kb = [
        [InlineKeyboardButton("🚀 Crear", callback_data="crear")],
        [InlineKeyboardButton("📄 Ver JSON", callback_data="ver")]
    ]

    await update.message.reply_text(
        "💀 Flujo listo (modo SaaS)",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# =========================
# 🎛 BOTONES
# =========================
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    wf = estado.get(uid)

    if not wf:
        return

    if q.data == "ver":
        txt = json.dumps(wf, indent=2)
        await context.bot.send_message(q.message.chat.id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif q.data == "crear":
        await context.bot.send_message(q.message.chat.id, "🚀 Enviando a n8n...")
        res = crear_n8n(wf)
        await context.bot.send_message(q.message.chat.id, str(res))

# =========================
# 🚀 START
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW SaaS REAL ACTIVO")
app.run_polling(drop_pending_updates=True)
