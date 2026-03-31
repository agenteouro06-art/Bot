import os
import json
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# =========================
# 🔐 CARGAR VARIABLES .ENV
# =========================
load_dotenv(dotenv_path="/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
N8N_API_KEY = os.getenv("N8N_API_KEY")
N8N_URL = os.getenv("N8N_URL")

# =========================
# 🚨 VALIDACIÓN INICIAL
# =========================
if not TELEGRAM_TOKEN:
    print("❌ ERROR: TELEGRAM_TOKEN no cargado")
    exit()

print("✅ BOT FUNCIONAL INICIADO")

# =========================
# 🤖 COMANDO START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 CLAW activo. Envíame lo que quieres automatizar.")

# =========================
# 🧠 GENERADOR DE FLUJOS
# =========================
def generar_flujo_base(texto_usuario):

    flujo = {
        "name": "Flujo AutoGenerado",
        "nodes": [
            {
                "id": "1",
                "name": "Inicio",
                "type": "n8n-nodes-base.start",
                "typeVersion": 1,
                "position": [100, 300],
                "parameters": {}
            },
            {
                "id": "2",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [300, 300],
                "parameters": {
                    "path": "webhook-auto",
                    "httpMethod": "POST"
                }
            },
            {
                "id": "3",
                "name": "Set Data",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [500, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "mensaje",
                                "value": texto_usuario
                            }
                        ]
                    }
                }
            },
            {
                "id": "4",
                "name": "Respuesta",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [700, 300],
                "parameters": {
                    "responseBody": "OK"
                }
            }
        ],
        "connections": {
            "Inicio": {
                "main": [
                    [
                        {
                            "node": "Webhook",
                            "type": "main",
                            "index": 0
                        }
                    ]
                ]
            },
            "Webhook": {
                "main": [
                    [
                        {
                            "node": "Set Data",
                            "type": "main",
                            "index": 0
                        }
                    ]
                ]
            },
            "Set Data": {
                "main": [
                    [
                        {
                            "node": "Respuesta",
                            "type": "main",
                            "index": 0
                        }
                    ]
                ]
            }
        },
        "settings": {}
    }

    return flujo

# =========================
# 🚀 ENVIAR A N8N
# =========================
def enviar_a_n8n(flujo):

    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(N8N_URL, headers=headers, json=flujo)

        print("📡 RESPUESTA N8N:", response.text)

        return response.json()

    except Exception as e:
        print("❌ ERROR N8N:", str(e))
        return {"error": str(e)}

# =========================
# 📩 MENSAJES
# =========================
async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text

    print(f"[MSG] {texto}")

    await update.message.reply_text("🧠 Procesando...")

    flujo = generar_flujo_base(texto)

    resultado = enviar_a_n8n(flujo)

    await update.message.reply_text(f"✅ Enviado a n8n:\n{resultado}")

# =========================
# 🚀 MAIN
# =========================
def main():

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))

    app.run_polling()

# =========================
# ▶️ EJECUCIÓN
# =========================
if __name__ == "__main__":
    main()
