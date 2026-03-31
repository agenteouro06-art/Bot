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
# 🧠 TEMPLATES BASE
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
        "name": "Validacion Pago",
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
# 🧠 MULTI AGENTE
# =========================

def agente_analista(texto):
    t = texto.lower()
    if "pago" in t or "banco" in t:
        return "pago"
    return "restaurante"

def agente_arquitecto(tipo):
    return template_pago() if tipo == "pago" else template_restaurante()

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
# 🔥 VALIDADOR
# =========================

def validar_workflow(wf):
    if not wf.get("nodes"):
        return False, "Sin nodos"

    for n in wf["nodes"]:
        if not n.get("type"):
            return False, "Nodo sin type"

    return True, "OK"

# =========================
# 🔥 LIMPIEZA PRO N8N
# =========================

def construir_payload(wf):
    nodes = []

    for i, n in enumerate(wf.get("nodes", [])):
        node = {
            "id": str(i + 1),
            "name": n.get("name", f"Node {i+1}"),
            "type": n.get("type"),
            "typeVersion": int(n.get("typeVersion", 1)),
            "position": n.get("position", [200 + i*250, 300]),
            "parameters": n.get("parameters", {})
        }
        nodes.append(node)

    payload = {
        "name": wf.get("name", "CLAW Flow"),
        "nodes": nodes,
        "connections": wf.get("connections", {})
    }

    # limpieza total
    return json.loads(json.dumps(payload))

# =========================
# 🚀 N8N CON RETRY INTELIGENTE
# =========================

def crear_workflow_con_retry(wf, max_intentos=3):
    for intento in range(1, max_intentos + 1):

        print(f"🚀 Intento {intento}")

        valido, msg = validar_workflow(wf)
        if not valido:
            print("❌ INVALIDO:", msg)
            wf = agente_optimizador(wf)
            continue

        payload = construir_payload(wf)

        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY.strip(),
                "Content-Type": "application/json"
            },
            data=json.dumps(payload),
            timeout=15
        )

        print("STATUS:", r.status_code)
        print("RESP:", r.text)

        if r.status_code in [200, 201]:
            try:
                data = r.json()
                if "id" in data:
                    return data
            except:
                pass

        # 🔥 SI FALLA → REGENERAR
        wf = agente_optimizador(wf)

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
        "⚙ Optimizando..."
    ]

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
        "🔥 FLOW PRO LISTO (con auto-retry)",
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
        await context.bot.send_message(chat, "🚀 Creando en n8n con retry inteligente...")

        res = crear_workflow_con_retry(estado[uid])

        if "id" in res:
            await context.bot.send_message(
                chat,
                f"✅ Workflow creado\nID: {res['id']}\n{N8N_URL}/workflow/{res['id']}"
            )
        else:
            await context.bot.send_message(chat, f"{res}")

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

print("🔥 CLAW GOD MODE ACTIVO")

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

app.run_polling(drop_pending_updates=True)
