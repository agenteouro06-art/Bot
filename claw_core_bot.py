import os
import json
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# =========================
# CARGAR VARIABLES
# =========================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = str(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# =========================
# IA (OPENROUTER)
# =========================
def generar_flujo(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "anthropic/claude-3-haiku",
        "messages": [
            {
                "role": "system",
                "content": "Genera SOLO JSON válido de n8n. Sin texto extra."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    res = requests.post(url, headers=headers, json=data)

    try:
        return res.json()["choices"][0]["message"]["content"]
    except:
        print("ERROR IA:", res.text)
        return None

# =========================
# LIMPIAR JSON PARA N8N
# =========================
def normalizar(wf):
    try:
        wf = json.loads(wf)
    except:
        return None

    limpio = {
        "name": wf.get("name", "Workflow IA"),
        "nodes": [],
        "connections": wf.get("connections", {}),
        "settings": {"executionOrder": "v1"}
    }

    for i, n in enumerate(wf.get("nodes", [])):
        limpio["nodes"].append({
            "id": str(i + 1),
            "name": n.get("name", f"Node {i+1}"),
            "type": n.get("type", "n8n-nodes-base.set"),
            "typeVersion": n.get("typeVersion", 1),
            "position": n.get("position", [200 + i*250, 300]),
            "parameters": n.get("parameters", {})
        })

    return limpio

# =========================
# ENVIAR A N8N
# =========================
def enviar_a_n8n(wf):
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }

    res = requests.post(f"{N8N_URL}/api/v1/workflows", headers=headers, json=wf)

    try:
        return res.json()
    except:
        return res.text

# =========================
# HANDLER TELEGRAM
# =========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    texto = update.message.text

    print(f"[MSG] {texto}")

    if user_id != ALLOWED_USER:
        await update.message.reply_text("❌ No autorizado")
        return

    await update.message.reply_text("🧠 Procesando...")

    flujo = generar_flujo(texto)

    if not flujo:
        await update.message.reply_text("❌ Error generando flujo")
        return

    limpio = normalizar(flujo)

    if not limpio:
        await update.message.reply_text("❌ JSON inválido")
        return

    res = enviar_a_n8n(limpio)

    await update.message.reply_text(f"✅ Enviado a n8n:\n{res}")

# =========================
# ERROR HANDLER
# =========================
async def error_handler(update, context):
    print(f"[ERROR] {context.error}")

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_error_handler(error_handler)

    print("🚀 BOT FUNCIONAL INICIADO")
    app.run_polling()

if __name__ == "__main__":
    main()
