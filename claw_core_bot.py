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
# 🧠 ANALISTA
# =========================
def analista(texto):
    t = texto.lower()
    if "pago" in t or "banco" in t:
        return "pago"
    if "restaurante" in t:
        return "restaurante"
    return "general"

# =========================
# 🏗 ARQUITECTO
# =========================
def arquitecto(tipo):

    if tipo == "pago":
        nodes = [
            {
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "parameters": {"path": "pago", "httpMethod": "POST"},
                "position": [200, 300]
            },
            {
                "name": "Comparar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "parameters": {
                    "functionCode": """
const texto = $json.texto || '';
const banco = $json.banco || '';
return [{ json: { aprobado: texto.includes(banco) } }];
"""
                },
                "position": [450, 300]
            }
        ]

    else:
        nodes = [
            {
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "parameters": {"path": "pedido", "httpMethod": "POST"},
                "position": [200, 300]
            },
            {
                "name": "Set Pedido",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "parameters": {
                    "values": {
                        "string": [{"name": "pedido", "value": "={{$json.body}}"}]
                    }
                },
                "position": [450, 300]
            }
        ]

    return {
        "name": f"CLAW Flow {random.randint(1,1000)}",
        "nodes": nodes
    }

# =========================
# 🔥 GENERADOR LIMPIO
# =========================
def construir_payload(wf):

    nodes = wf["nodes"]

    # conexiones reales válidas
    connections = {}
    for i in range(len(nodes)-1):
        connections[nodes[i]["name"]] = {
            "main": [[{
                "node": nodes[i+1]["name"],
                "type": "main",
                "index": 0
            }]]
        }

    payload = {
        "name": wf["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": {}  # 🔥 CLAVE ABSOLUTA
    }

    return payload

# =========================
# 🤖 REPARADOR
# =========================
def reparar(payload, error):

    if "settings" in error:
        payload["settings"] = {}

    if "connections" in error:
        payload["connections"] = {}

    return payload

# =========================
# 🚀 CREAR EN N8N (FIX REAL)
# =========================
def crear_n8n(payload):

    for intento in range(3):
        print(f"🚀 Intento {intento+1}")

        clean_payload = construir_payload(payload)

        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=clean_payload
        )

        print("STATUS:", r.status_code)
        print("RESP:", r.text)

        if r.status_code in [200, 201]:
            return r.json()

        payload = reparar(payload, r.text)

    return {"error": "❌ Falló después de 3 intentos"}

# =========================
# 🏢 MODO AGENCIA
# =========================
def generar_oferta(tipo):

    if tipo == "pago":
        return """
💰 SERVICIO: Validación automática de pagos

✔ Detecta transferencias
✔ Evita fraudes
✔ Automatiza confirmación

Precio sugerido: $300 - $800 USD
"""

    if tipo == "restaurante":
        return """
🍔 SERVICIO: Bot de pedidos automático

✔ Recibe pedidos 24/7
✔ Reduce errores humanos
✔ Mejora atención

Precio sugerido: $200 - $600 USD
"""

    return "💡 Flujo automatizado listo para vender"

# =========================
# 🤖 MOTOR
# =========================
async def procesar(update, context, texto):

    uid = update.effective_user.id

    pasos = [
        "🧠 Analizando negocio...",
        "🏗 Diseñando sistema...",
        "⚙ Generando flujo...",
        "🔍 Validando...",
        "💰 Preparando oferta..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.2)

    tipo = analista(texto)
    wf = arquitecto(tipo)

    estado[uid] = wf

    oferta = generar_oferta(tipo)

    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="ver")
        ]
    ]

    await update.message.reply_text(
        f"✅ Sistema listo\n\n{oferta}",
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
        await context.bot.send_message(chat, "🚀 Creando flujo en n8n...")
        res = crear_n8n(estado[uid])
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

print("💀 CLAW AGENCIA AUTOMATIZADA ACTIVA")
app.run_polling()
