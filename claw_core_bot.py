import os
import json
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# ================================
# CARGAR VARIABLES
# ================================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
N8N_URL = os.getenv("N8N_URL")  # ejemplo: http://localhost:5678/api/v1/workflows
N8N_API_KEY = os.getenv("N8N_API_KEY")

# ================================
# GENERADOR DE FLUJOS (CORREGIDO)
# ================================
def generar_flujo(prompt):

    return {
        "name": "Claw Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [200, 300],
                "parameters": {
                    "path": "claw",
                    "httpMethod": "POST"
                }
            },
            {
                "id": "2",
                "name": "Responder",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [400, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "respuesta",
                                "value": "Flujo generado correctamente"
                            }
                        ]
                    }
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [
                    [
                        {
                            "node": "Responder",
                            "type": "main",
                            "index": 0
                        }
                    ]
                ]
            }
        },
        "settings": {}
    }

# ================================
# ENVIAR A N8N (CORREGIDO)
# ================================
def enviar_a_n8n(flujo):

    headers = {
        "Content-Type": "application/json",
        "X-N8N-API-KEY": N8N_API_KEY
    }

    try:
        response = requests.post(
            N8N_URL,
            headers=headers,
            data=json.dumps(flujo)
        )

        print("📡 STATUS:", response.status_code)
        print("📡 RESPUESTA RAW:", response.text)

        if response.status_code == 401:
            return "❌ ERROR: API KEY inválida o no autorizada"

        return response.text

    except Exception as e:
        return f"❌ ERROR CONEXIÓN N8N: {str(e)}"

# ================================
# TELEGRAM HANDLER
# ================================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    mensaje = update.message.text
    print("[MSG]", mensaje)

    await update.message.reply_text("🧠 Procesando...")

    flujo = generar_flujo(mensaje)

    respuesta = enviar_a_n8n(flujo)

    await update.message.reply_text(f"🚀 Resultado:\n{respuesta}")

# ================================
# MAIN
# ================================
def main():

    print("✅ BOT FUNCIONAL INICIADO")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling()

if __name__ == "__main__":
    main()
