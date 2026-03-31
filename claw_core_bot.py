import os
import json
import asyncio
import random
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# =========================
# 🔐 ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

estado = {}

# =========================
# 🧠 AGENTE ANALISTA
# =========================
def analista(texto):
    t = texto.lower()

    if "restaurante" in t:
        return "restaurante"
    if "pago" in t or "banco" in t:
        return "pago"
    return "general"

# =========================
# 🏗 AGENTE ARQUITECTO
# =========================
def arquitecto(tipo):
    if tipo == "pago":
        return {
            "name": f"Validacion Pago v{random.randint(1,100)}",
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
            },
            "settings": {}
        }

    # restaurante template
    return {
        "name": f"Pedidos Restaurante v{random.randint(1,100)}",
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
        },
        "settings": {}
    }

# =========================
# 🎨 AGENTE DISEÑADOR
# =========================
def diseñador(wf):
    wf["name"] += " PRO"
    return wf

# =========================
# ⚙️ AGENTE OPTIMIZADOR
# =========================
def optimizador(wf):
    if random.random() > 0.5:
        wf["nodes"].append({
            "name": "Extra",
            "type": "n8n-nodes-base.set",
            "typeVersion": 2,
            "position": [700, 300],
            "parameters": {
                "values": {
                    "string": [{"name": "status", "value": "ok"}]
                }
            }
        })
    return wf

# =========================
# 🔍 VALIDADOR + FIX
# =========================
def limpiar(wf):
    nombres = set()
    nodos = []

    for i, n in enumerate(wf["nodes"]):
        if n["name"] in nombres:
            continue
        nombres.add(n["name"])

        n["position"] = [200 + i*250, 300]
        n["parameters"] = n.get("parameters", {})
        n["typeVersion"] = n.get("typeVersion", 1)

        nodos.append(n)

    wf["nodes"] = nodos

    # reconstruir conexiones
    conexiones = {}
    for i in range(len(nodos)-1):
        conexiones[nodos[i]["name"]] = {
            "main": [[{"node": nodos[i+1]["name"], "type": "main", "index": 0}]]
        }

    wf["connections"] = conexiones

    wf["settings"] = {}

    return wf

# =========================
# 🤖 AGENTE REPARADOR
# =========================
def reparar_por_error(wf, error):
    error = error.lower()

    if "settings" in error:
        wf["settings"] = {}

    if "nodes" in error:
        wf["nodes"] = wf["nodes"][:2]

    return wf

# =========================
# 🚀 CREAR CON IA + RETRY
# =========================
def crear_saas(wf):
    for intento in range(3):
        print(f"🚀 Intento {intento+1}")

        wf = limpiar(wf)

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

        wf = reparar_por_error(wf, r.text)

    return {"error": "❌ Falló después de 3 intentos"}

# =========================
# 🤖 MOTOR
# =========================
async def procesar(update, context, texto):
    uid = update.effective_user.id

    pasos = [
        "🧠 Analista IA",
        "🏗 Arquitecto IA",
        "🎨 Diseñador IA",
        "⚙ Optimizador IA",
        "🔍 Validando",
        "🛠 Reparando",
        "🚀 Listo"
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.2)

    tipo = analista(texto)
    wf = arquitecto(tipo)
    wf = diseñador(wf)
    wf = optimizador(wf)

    estado[uid] = wf

    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="ver")
        ]
    ]

    await update.message.reply_text("💰 Flujo SaaS listo para vender", reply_markup=InlineKeyboardMarkup(kb))

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
        await context.bot.send_message(chat, "🚀 Creando flujo SaaS...")
        res = crear_saas(estado[uid])
        await context.bot.send_message(chat, str(res))

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
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("💀 CLAW SaaS MODE ACTIVADO")
app.run_polling()
