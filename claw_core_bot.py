import os
import json
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = "TU_TOKEN_AQUI"
N8N_URL = "http://localhost:5678/api/v1/workflows"
N8N_API_KEY = "TU_API_KEY_N8N"

# =========================
# NORMALIZADOR n8n (CLAVE)
# =========================

def normalizar(wf):
    try:
        wf = json.loads(wf)
    except:
        return None

    limpio = {
        "name": wf.get("name", "Workflow IA"),
        "nodes": [],
        "connections": wf.get("connections", {})
    }

    for i, n in enumerate(wf.get("nodes", [])):

        # 🔥 FIX POSITION
        pos = n.get("position", [200 + i*300, 300])
        if not isinstance(pos, list) or len(pos) != 2:
            pos = [200 + i*300, 300]

        limpio["nodes"].append({
            "id": str(i + 1),
            "name": n.get("name", f"Node {i+1}"),
            "type": n.get("type", "n8n-nodes-base.set"),
            "typeVersion": n.get("typeVersion", 1),
            "position": pos,
            "parameters": n.get("parameters", {})
        })

    return limpio

# =========================
# ENVÍO A n8n
# =========================

def enviar_a_n8n(workflow):
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(N8N_URL, headers=headers, json=workflow)

    try:
        return response.json()
    except:
        return {"error": response.text}

# =========================
# GENERADOR DE FLUJOS (SIN IA)
# =========================

def generar_flujo_basico():
    return {
        "name": "Verificación Transferencias",
        "nodes": [
            {
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "position": [200, 300],
                "parameters": {
                    "path": "verificacion",
                    "httpMethod": "POST"
                }
            },
            {
                "name": "Leer Email",
                "type": "n8n-nodes-base.emailReadImap",
                "position": [500, 300],
                "parameters": {
                    "mailbox": "INBOX"
                }
            },
            {
                "name": "Comparar",
                "type": "n8n-nodes-base.if",
                "position": [800, 300],
                "parameters": {
                    "conditions": {
                        "string": [
                            {
                                "value1": "={{$json[\"referencia\"]}}",
                                "operation": "contains",
                                "value2": "={{$json[\"correo\"]}}"
                            }
                        ]
                    }
                }
            },
            {
                "name": "Respuesta OK",
                "type": "n8n-nodes-base.set",
                "position": [1100, 200],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "estado",
                                "value": "verificado"
                            }
                        ]
                    }
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Leer Email", "type": "main", "index": 0}]]
            },
            "Leer Email": {
                "main": [[{"node": "Comparar", "type": "main", "index": 0}]]
            },
            "Comparar": {
                "main": [
                    [{"node": "Respuesta OK", "type": "main", "index": 0}],
                    []
                ]
            }
        }
    }

# =========================
# HANDLER TELEGRAM
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text

    print("[MSG]", texto)

    await update.message.reply_text("🧠 Procesando...")

    # 🔥 GENERAR FLUJO (puedes mejorar lógica aquí)
    flujo = generar_flujo_basico()

    # 🔥 NORMALIZAR (CLAVE)
    flujo_limpio = normalizar(json.dumps(flujo))

    if not flujo_limpio:
        await update.message.reply_text("❌ Error generando flujo")
        return

    # 🔥 ENVIAR A n8n
    res = enviar_a_n8n(flujo_limpio)

    print("✅ Enviado a n8n:", res)

    await update.message.reply_text(f"✅ Flujo enviado:\n{res}")

# =========================
# MAIN
# =========================

def main():
    print("🚀 BOT FUNCIONAL INICIADO")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling()

if __name__ == "__main__":
    main()
