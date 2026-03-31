import os
import json
import asyncio
import random
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# =========================
# 🔥 ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

estado = {}

# =========================
# 🧠 TEMPLATES
# =========================

def template_restaurante():
    return {
        "name": "Pedidos Restaurante",
        "nodes": [
            {
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "pedido",
                    "httpMethod": "POST"
                }
            },
            {
                "name": "Set Pedido",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [450, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "pedido", "value": "={{$json.body}}"}
                        ]
                    }
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Set Pedido", "type": "main", "index": 0}]]
            }
        }
    }

def template_pago():
    return {
        "name": "Validación Pago",
        "nodes": [
            {
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "pago",
                    "httpMethod": "POST"
                }
            },
            {
                "name": "Comparar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [450, 300],
                "parameters": {
                    "functionCode": """
const texto = $json.texto || '';
const banco = $json.banco || '';

return [{
  json: {
    aprobado: texto.includes(banco)
  }
}]
"""
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Comparar", "type": "main", "index": 0}]]
            }
        }
    }

# =========================
# 🧠 MULTI-AGENTE
# =========================

def agente_analista(texto):
    t = texto.lower()
    if "restaurante" in t:
        return "restaurante"
    if "pago" in t or "banco" in t:
        return "pago"
    return "restaurante"

def agente_arquitecto(tipo):
    return template_restaurante() if tipo == "restaurante" else template_pago()

def agente_diseñador(wf):
    wf["name"] += f" v{random.randint(1,100)}"
    return wf

def agente_optimizador(wf):
    if random.random() > 0.5:
        wf["nodes"].append({
            "name": "Extra",
            "type": "n8n-nodes-base.set",
            "typeVersion": 2,
            "position": [700, 300],
            "parameters": {
                "values": {
                    "string": [{"name": "extra", "value": "ok"}]
                }
            }
        })
    return wf

# =========================
# 🔥 LIMPIEZA PARA N8N API
# =========================

def limpiar_nodos(nodes):
    clean = []
    for i, n in enumerate(nodes):
        clean.append({
            "id": str(i + 1),
            "name": n.get("name"),
            "type": n.get("type"),
            "typeVersion": n.get("typeVersion", 1),
            "position": n.get("position", [200 + i*250, 300]),
            "parameters": n.get("parameters", {})
        })
    return clean

def construir_payload(wf):
    return {
        "name": wf.get("name", "CLAW Flow"),
        "nodes": limpiar_nodos(wf.get("nodes", [])),
        "connections": wf.get("connections", {})
    }

# =========================
# 🚀 N8N API
# =========================

def crear_workflow(wf):
    payload = construir_payload(wf)

    r = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        headers={
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=15
    )

    print("STATUS:", r.status_code)
    print("RESP:", r.text)

    if r.status_code == 401:
        return {"error": "❌ API KEY inválida"}

    try:
        return r.json()
    except:
        return {"error": r.text}

# =========================
# 🤖 MOTOR
# =========================

async def procesar(update, context, texto):
    uid = update.effective_user.id

    pasos = ["🧠 Analizando...", "🏗 Diseñando...", "⚙ Optimizando..."]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.3)

    tipo = agente_analista(texto)
    wf = agente_arquitecto(tipo)
    wf = agente_diseñador(wf)
    wf = agente_optimizador(wf)

    estado[uid] = wf

    kb = [
        [InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
         InlineKeyboardButton("📄 Ver JSON", callback_data="ver")]
    ]

    await update.message.reply_text(
        "🔥 FLOW LISTO (sin errores API)",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# =========================
# 🎛 BOTONES
# =========================

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    chat = query.message.chat.id

    if query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await context.bot.send_message(chat, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        await context.bot.send_message(chat, "🚀 Creando en n8n...")

        res = crear_workflow(estado[uid])

        if "id" in res:
            await context.bot.send_message(
                chat,
                f"✅ Workflow creado\nID: {res['id']}\n{N8N_URL}/workflow/{res['id']}"
            )
        else:
            await context.bot.send_message(chat, f"❌ Error:\n{res}")

# =========================
# 📩 MENSAJES
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)

# =========================
# 🚀 START
# =========================

print("🔥 CLAW GIFHUD PRO ACTIVO")

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

app.run_polling(drop_pending_updates=True)
