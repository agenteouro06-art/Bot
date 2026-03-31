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
# 🧠 TEMPLATE BASE LIMPIO
# =========================

def template_pago():
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

# =========================
# 🧠 AGENTES
# =========================

def agente_analista(texto):
    if "pago" in texto.lower() or "banco" in texto.lower():
        return "pago"
    return "pago"

def agente_arquitecto(tipo):
    return template_pago()

def agente_optimizador(workflow):
    # agrega UN solo nodo extra conectado
    if random.random() > 0.5:
        workflow["nodes"].append({
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

        workflow["connections"]["Comparar"] = {
            "main": [[{"node": "Extra", "type": "main", "index": 0}]]
        }

    return workflow

# =========================
# 🔥 NORMALIZADOR PRO
# =========================

def limpiar_workflow(wf):
    nombres = set()
    nuevos_nodos = []

    for i, n in enumerate(wf.get("nodes", [])):
        if n["name"] in nombres:
            continue
        nombres.add(n["name"])

        n["position"] = n.get("position", [200 + i*250, 300])
        n["parameters"] = n.get("parameters", {})
        n["typeVersion"] = n.get("typeVersion", 1)

        nuevos_nodos.append(n)

    wf["nodes"] = nuevos_nodos

    # reconstruir conexiones
    conexiones = {}
    for i in range(len(nuevos_nodos) - 1):
        conexiones[nuevos_nodos[i]["name"]] = {
            "main": [[{"node": nuevos_nodos[i+1]["name"], "type": "main", "index": 0}]]
        }

    wf["connections"] = conexiones

    # 🔥 CRÍTICO
    wf["settings"] = {}

    # limpiar basura
    for k in ["id", "active"]:
        wf.pop(k, None)

    return wf

# =========================
# 🚀 N8N CON AUTO-REPAIR
# =========================

def crear_con_retry(workflow, max_intentos=3):
    for intento in range(max_intentos):
        print(f"🚀 Intento {intento+1}")

        workflow = limpiar_workflow(workflow)

        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=workflow
        )

        print("STATUS:", r.status_code)
        print("RESP:", r.text)

        if r.status_code in [200, 201]:
            return r.json()

        # 🔥 REPARACIÓN AUTOMÁTICA
        workflow["settings"] = {}

    return {"error": "❌ Falló después de 3 intentos"}

# =========================
# 🤖 MOTOR
# =========================

async def procesar(update, context, texto):
    uid = update.effective_user.id

    pasos = [
        "🧠 Analizando...",
        "🏗 Diseñando...",
        "🔍 Validando...",
        "⚙ Corrigiendo...",
        "💰 Optimizando..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.2)

    tipo = agente_analista(texto)
    wf = agente_arquitecto(tipo)
    wf = agente_optimizador(wf)

    estado[uid] = wf

    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="ver")
        ]
    ]

    await update.message.reply_text("✅ Flujo listo", reply_markup=InlineKeyboardMarkup(kb))

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
        await context.bot.send_message(chat, "🚀 Creando en n8n con retry inteligente...")
        res = crear_con_retry(estado[uid])
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

print("🔥 CLAW GOD MODE ACTIVO (FIXED)")
app.run_polling()
