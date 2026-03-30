import os
import json
import asyncio
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    CommandHandler,
    filters
)

# ✅ FIX COMILLAS
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER       = int(os.getenv("ALLOWED_USER"))
N8N_URL            = os.getenv("N8N_URL")
N8N_API_KEY        = os.getenv("N8N_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ================================
# 🧠 PROMPT INTELIGENTE (MEJORADO)
# ================================
SYSTEM_PROMPT = """
Eres CLAW MODO BRUTAL.

OBJETIVO:
Crear workflows reales, funcionales y COMPLETOS para n8n.

MULTIAGENTE:
[ANALISTA] entiende negocio
[ARQUITECTO] define nodos
[DISENADOR] crea JSON
[VALIDADOR] revisa errores
[EJECUTOR] define APIs
[OPTIMIZADOR] deja listo para vender

REGLAS:
- SIEMPRE devolver JSON válido
- SIEMPRE conectar TODOS los nodos
- NUNCA devolver workflow incompleto
- Si falta info → asumir valores por defecto funcionales

IMPORTANTE:
Responder SIEMPRE con:

1. Explicación breve
2. JSON entre ```json ... ```
"""

# ================================
# 🤖 IA ROBUSTA (FIX ERROR 'choices')
# ================================
def llamar_ia(prompt):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60
        )

        data = r.json()

        if "choices" not in data:
            return {"texto": str(data), "workflow_json": None}

        respuesta = data["choices"][0]["message"]["content"]

    except Exception as e:
        return {"texto": f"Error IA: {e}", "workflow_json": None}

    # 🔥 EXTRAER JSON
    workflow_json = None
    if "```" in respuesta:
        try:
            json_str = respuesta.split("```json")[-1].split("```")[0]
            workflow_json = json.loads(json_str)
        except:
            workflow_json = None

    return {
        "texto": respuesta,
        "workflow_json": workflow_json
    }

# ================================
# 🔥 FALLBACK (SI IA FALLA)
# ================================
def workflow_fallback():
    return {
        "name": "Fallback Restaurante",
        "nodes": [
            {
                "parameters": {"path": "pedido", "httpMethod": "POST"},
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300]
            },
            {
                "parameters": {"operation": "read", "sheetId": "ID"},
                "id": "2",
                "name": "Google Sheets",
                "type": "n8n-nodes-base.googleSheets",
                "typeVersion": 4,
                "position": [400, 300]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Google Sheets", "type": "main", "index": 0}]]
            }
        }
    }

# ================================
# 🚀 N8N
# ================================
def crear_workflow(workflow):
    try:
        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=workflow
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# ================================
# 🤖 TELEGRAM
# ================================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text

    # 🔥 EFECTO ESCRIBIENDO
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    # MULTIAGENTE VISUAL
    fases = [
        "🧠 ANALISTA...",
        "🏗 ARQUITECTO...",
        "🎨 DISEÑADOR...",
        "🔍 VALIDADOR...",
        "⚙️ EJECUTOR...",
        "💰 OPTIMIZADOR..."
    ]

    for f in fases:
        await update.message.reply_text(f)
        await asyncio.sleep(0.4)

    resultado = llamar_ia(texto)

    # 🔥 SI IA FALLA → FALLBACK
    if not resultado["workflow_json"]:
        await update.message.reply_text("⚠ IA falló → usando fallback funcional")
        wf = workflow_fallback()
    else:
        wf = resultado["workflow_json"]

    crear_workflow(wf)

    await update.message.reply_text("🚀 Workflow creado correctamente")

# ================================
# ▶️ START
# ================================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("🔥 CLAW MODO BRUTAL ACTIVO")
app.run_polling()
