import os
import json
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# =========================
# 🔐 CARGAR .ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TOKEN = os.getenv("TELEGRAM_TOKEN")
N8N_API_KEY = os.getenv("N8N_API_KEY")
N8N_URL = os.getenv("N8N_URL")

if not TOKEN:
    print("❌ TOKEN NO CARGADO")
    exit()

print("🔥 BOT MODO DIOS INICIADO")

# =========================
# 🧠 DETECCIÓN DE INTENCIÓN
# =========================
def detectar_intencion(texto):

    texto = texto.lower()

    if "whatsapp" in texto and "captura" in texto:
        return "verificar_pago"

    if "correo" in texto or "email" in texto:
        return "leer_email"

    if "webhook" in texto:
        return "webhook"

    return "basico"

# =========================
# 🧠 GENERADOR AVANZADO
# =========================
def generar_flujo(intencion, texto):

    base = {
        "name": "AUTO - " + intencion,
        "nodes": [],
        "connections": {},
        "settings": {}
    }

    # =====================
    # 💳 CASO REAL: PAGOS
    # =====================
    if intencion == "verificar_pago":

        base["nodes"] = [
            {
                "id": "1",
                "name": "Webhook Entrada",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [100, 300],
                "parameters": {
                    "path": "verificar-pago",
                    "httpMethod": "POST"
                }
            },
            {
                "id": "2",
                "name": "Leer Email Banco",
                "type": "n8n-nodes-base.emailReadImap",
                "typeVersion": 1,
                "position": [300, 300],
                "parameters": {
                    "mailbox": "INBOX"
                }
            },
            {
                "id": "3",
                "name": "Comparar",
                "type": "n8n-nodes-base.if",
                "typeVersion": 1,
                "position": [500, 300],
                "parameters": {
                    "conditions": {
                        "string": [
                            {
                                "value1": "={{$json[\"referencia\"]}}",
                                "operation": "contains",
                                "value2": "={{$node[\"Leer Email Banco\"].json[\"text\"]}}"
                            }
                        ]
                    }
                }
            },
            {
                "id": "4",
                "name": "Confirmar",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [700, 200],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "estado", "value": "APROBADO"}
                        ]
                    }
                }
            },
            {
                "id": "5",
                "name": "Rechazar",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [700, 400],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "estado", "value": "RECHAZADO"}
                        ]
                    }
                }
            }
        ]

        base["connections"] = {
            "Webhook Entrada": {
                "main": [[{"node": "Leer Email Banco", "type": "main", "index": 0}]]
            },
            "Leer Email Banco": {
                "main": [[{"node": "Comparar", "type": "main", "index": 0}]]
            },
            "Comparar": {
                "main": [
                    [{"node": "Confirmar", "type": "main", "index": 0}],
                    [{"node": "Rechazar", "type": "main", "index": 0}]
                ]
            }
        }

    # =====================
    # 🔗 WEBHOOK SIMPLE
    # =====================
    else:

        base["nodes"] = [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [200, 300],
                "parameters": {
                    "path": "auto",
                    "httpMethod": "POST"
                }
            },
            {
                "id": "2",
                "name": "Responder",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [400, 300],
                "parameters": {
                    "responseBody": "OK"
                }
            }
        ]

        base["connections"] = {
            "Webhook": {
                "main": [[{"node": "Responder", "type": "main", "index": 0}]]
            }
        }

    return base

# =========================
# 🛡️ VALIDADOR (CLAVE)
# =========================
def validar_flujo(flujo):

    if "name" not in flujo:
        flujo["name"] = "AUTO"

    if "settings" not in flujo:
        flujo["settings"] = {}

    for node in flujo["nodes"]:
        if "position" not in node:
            node["position"] = [0, 0]

    return flujo

# =========================
# 🚀 ENVIAR A N8N
# =========================
def enviar_n8n(flujo):

    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(N8N_URL, headers=headers, json=flujo)
        print("📡", r.text)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# =========================
# 📩 MENSAJES TELEGRAM
# =========================
async def mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):

    texto = update.message.text
    print("[MSG]", texto)

    await update.message.reply_text("🧠 Analizando...")

    intencion = detectar_intencion(texto)

    flujo = generar_flujo(intencion, texto)
    flujo = validar_flujo(flujo)

    resultado = enviar_n8n(flujo)

    await update.message.reply_text(f"✅ Flujo creado:\n{json.dumps(resultado, indent=2)}")

# =========================
# ▶️ MAIN
# =========================
def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("🔥 MODO DIOS ACTIVO")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje))

    app.run_polling()

if __name__ == "__main__":
    main()
