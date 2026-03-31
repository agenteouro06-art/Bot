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
# ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

estado = {}

# =========================
# GENERADOR REAL
# =========================

def generar_flujo():
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
            }
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Comparar","type": "main","index": 0}]]}
        }
    }

# =========================
# LIMPIEZA TOTAL
# =========================

def limpiar(workflow):
    keys = ["id","active","versionId","createdAt","updatedAt","meta","pinData","staticData"]
    for k in keys:
        workflow.pop(k, None)
    return workflow

# =========================
# PROBAR SETTINGS DINÁMICO
# =========================

def intentar_crear(workflow):
    variantes = [
        lambda wf: {**wf, "settings": {}},
        lambda wf: wf,  # sin settings
        lambda wf: {**wf, "settings": {"saveExecutionProgress": True}},
    ]

    for intento in range(3):
        print(f"\n🚀 Intento {intento+1}")

        for i, variante in enumerate(variantes):
            wf = limpiar(json.loads(json.dumps(workflow)))
            wf = variante(wf)

            print(f"👉 Variante {i+1}")

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

    return {"error": "❌ Falló después de probar TODAS las variantes"}

# =========================
# BOT
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    wf = generar_flujo()
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
        res = intentar_crear(wf)
        await context.bot.send_message(query.message.chat.id, str(res))

# =========================
# START
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW GOD MODE FIX FINAL ACTIVO")
app.run_polling()
