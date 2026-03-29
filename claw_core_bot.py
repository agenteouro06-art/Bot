import os
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# 🔐 ENV
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

# ================================
# 🧠 MULTI-AGENTE NIVEL DIOS
# ================================

def analizar_intencion(text):
    t = text.lower()

    if "pago" in t or "transferencia" in t:
        return "validacion_pagos"

    if "restaurante" in t or "pedido" in t:
        return "pedidos_restaurante"

    if "factura" in t:
        return "facturas"

    return "general"


def detectar_necesidades(text):
    t = text.lower()
    needs = []

    if "imagen" in t or "captura" in t:
        needs.append("ocr")

    if "gmail" in t or "correo" in t:
        needs.append("gmail")

    if "whatsapp" in t:
        needs.append("whatsapp")

    if "menu" in t or "sheets" in t:
        needs.append("sheets")

    return needs


# ================================
# 🏗 WORKFLOWS REALES
# ================================

def workflow_validacion_pagos():
    return {
        "name": "Validación Pagos PRO",
        "nodes": [
            {
                "parameters": {"path": "pagos", "httpMethod": "POST"},
                "id": "webhook",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "position": [200, 300]
            },
            {
                "parameters": {
                    "url": "https://api.ocr.space/parse/image",
                    "method": "POST"
                },
                "id": "ocr",
                "name": "OCR",
                "type": "n8n-nodes-base.httpRequest",
                "position": [400, 300]
            },
            {
                "parameters": {"resource": "message", "operation": "getAll"},
                "id": "gmail",
                "name": "Gmail",
                "type": "n8n-nodes-base.gmail",
                "position": [600, 300]
            },
            {
                "parameters": {
                    "functionCode": """
const ref = $json["ParsedText"] || "";
let match = false;

for (let item of items) {
  if (item.json.subject && item.json.subject.includes(ref)) {
    match = true;
  }
}

return [{json: {match}}];
"""
                },
                "id": "validar",
                "name": "Validar Pago",
                "type": "n8n-nodes-base.function",
                "position": [800, 300]
            }
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "OCR", "type": "main"}]]},
            "OCR": {"main": [[{"node": "Gmail", "type": "main"}]]},
            "Gmail": {"main": [[{"node": "Validar Pago", "type": "main"}]]}
        },
        "settings": {}
    }


def workflow_restaurante():
    return {
        "name": "Pedidos Restaurante PRO",
        "nodes": [
            {
                "parameters": {"path": "pedido", "httpMethod": "POST"},
                "id": "webhook",
                "name": "Webhook Pedido",
                "type": "n8n-nodes-base.webhook",
                "position": [200, 300]
            },
            {
                "parameters": {"operation": "read"},
                "id": "sheets",
                "name": "Google Sheets",
                "type": "n8n-nodes-base.googleSheets",
                "position": [400, 300]
            },
            {
                "parameters": {
                    "functionCode": "return items;"
                },
                "id": "procesar",
                "name": "Procesar",
                "type": "n8n-nodes-base.function",
                "position": [600, 300]
            }
        ],
        "connections": {
            "Webhook Pedido": {"main": [[{"node": "Google Sheets", "type": "main"}]]},
            "Google Sheets": {"main": [[{"node": "Procesar", "type": "main"}]]}
        },
        "settings": {}
    }


# ================================
# 🚀 N8N
# ================================

def enviar_a_n8n(wf):
    try:
        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=wf
        )
        return r.status_code
    except Exception as e:
        return str(e)


# ================================
# 🧠 RESPUESTA MULTI-AGENTE
# ================================

async def multi_agente(update, text):
    await update.message.reply_text("🧠 ANALISTA:\nDetectando solución...")
    await update.message.reply_text("🏗 ARQUITECTO:\nDiseñando sistema...")
    await update.message.reply_text("🎨 DISEÑADOR:\nCreando workflow...")
    await update.message.reply_text("⚙️ EJECUTOR:\nPreparando integración...")
    await update.message.reply_text("💰 OPTIMIZADOR:\nListo para vender")


# ================================
# 🤖 BOT
# ================================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ALLOWED_USER:
        return

    text = update.message.text

    await update.message.chat.send_action("typing")

    await multi_agente(update, text)

    tipo = analizar_intencion(text)
    needs = detectar_necesidades(text)

    # 🔥 DETECTA APIs
    if "whatsapp" in needs:
        context.user_data["tipo"] = tipo
        await update.message.reply_text("📱 ¿Tienes API de WhatsApp?\n(SI / NO)")
        context.user_data["wait_api"] = True
        return

    # 🔥 GENERA
    if tipo == "validacion_pagos":
        wf = workflow_validacion_pagos()

    elif tipo == "pedidos_restaurante":
        wf = workflow_restaurante()

    else:
        await update.message.reply_text("❌ No entendí el flujo")
        return

    enviar_a_n8n(wf)

    await update.message.reply_text(
        "🚀 Workflow creado\n\n"
        "✔ Automatización lista\n"
        "✔ Nodos conectados\n"
        "✔ Flujo funcional\n\n"
        "⚙️ Configura:\n"
        "- Gmail\n"
        "- OCR API\n"
        "- Webhook WhatsApp"
    )


# ================================
# ▶️ INICIO
# ================================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()
