import os
import json
import asyncio
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# =============================
# 🔥 CONFIG
# =============================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER   = int(os.getenv("ALLOWED_USER"))
N8N_URL        = os.getenv("N8N_URL")
N8N_API_KEY    = os.getenv("N8N_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

estado = {}
historial = []

# =============================
# 🤖 IA REAL
# =============================
def llamar_ia(prompt):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-3-haiku",
                "messages": [
                    {"role": "system", "content": "Eres experto en n8n. SOLO devuelves JSON válido."},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=25
        )
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("ERROR IA:", e)
        return None

# =============================
# 🧹 LIMPIAR JSON
# =============================
def limpiar_json(texto):
    try:
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        return json.loads(texto[inicio:fin])
    except:
        return None

# =============================
# 🧠 VALIDADOR
# =============================
def validar(workflow):
    if not workflow:
        return False
    if "nodes" not in workflow or len(workflow["nodes"]) < 2:
        return False
    if "connections" not in workflow:
        return False
    return True

# =============================
# 🧬 DETECTOR DE INTENCIÓN
# =============================
def detectar_tipo(texto):
    t = texto.lower()
    if "pedido" in t or "restaurante" in t:
        return "pedido"
    elif "pago" in t or "transferencia" in t:
        return "pago"
    return "basico"

# =============================
# 🧬 MARKETPLACE BASE
# =============================
def flow_pedidos():
    return {
        "name": "Pedidos Restaurante",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200,300],
                "parameters": {
                    "path": "pedido",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },
            {
                "id": "2",
                "name": "Google Sheets",
                "type": "n8n-nodes-base.googleSheets",
                "typeVersion": 4,
                "position": [400,300],
                "parameters": {
                    "operation": "read"
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node":"Google Sheets","type":"main","index":0}]]
            }
        },
        "settings": {}
    }

def flow_pagos():
    return {
        "name": "Validar Pagos",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200,300],
                "parameters": {
                    "path": "pago",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },
            {
                "id": "2",
                "name": "Set",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [400,300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name":"estado","value":"recibido"}
                        ]
                    }
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node":"Set","type":"main","index":0}]]
            }
        },
        "settings": {}
    }

# =============================
# 🔥 NORMALIZAR
# =============================
def normalizar(workflow):
    for k in ["id","active","meta","versionId","pinData"]:
        workflow.pop(k, None)

    for node in workflow["nodes"]:
        node["parameters"] = node.get("parameters", {})
        node["position"] = node.get("position", [300,300])
        node["typeVersion"] = node.get("typeVersion", 1)

    return workflow

# =============================
# 🚀 CREAR EN N8N
# =============================
def crear_workflow(workflow):
    try:
        workflow = normalizar(workflow)

        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=workflow,
            timeout=20
        )

        print("N8N:", r.text)

        if r.status_code != 200:
            return {"error": r.text}

        return {"ok": True}

    except Exception as e:
        return {"error": str(e)}

# =============================
# 🧠 MOTOR IA + FALLBACK
# =============================
async def procesar(update, context, texto):
    uid = update.effective_user.id

    pasos = [
        "🧠 ANALISTA IA...",
        "🏗 ARQUITECTO IA...",
        "🎨 DISEÑADOR IA...",
        "🔍 VALIDANDO JSON...",
        "⚙ CORRIGIENDO...",
        "💰 OPTIMIZANDO..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.3)

    raw = llamar_ia(f"Genera workflow n8n JSON:\n{texto}")
    wf = limpiar_json(raw)

    if not validar(wf):
        await update.message.reply_text("⚠ IA falló → usando marketplace")

        tipo = detectar_tipo(texto)

        if tipo == "pedido":
            wf = flow_pedidos()
        else:
            wf = flow_pagos()

    estado[uid] = wf
    historial.append(wf)

    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="ver")
        ],
        [
            InlineKeyboardButton("🧠 Mejorar IA", callback_data="mejorar"),
            InlineKeyboardButton("🔄 Regenerar", callback_data="regen")
        ]
    ]

    await update.message.reply_text(
        "💀 ULTRA FLOW listo",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# =============================
# 🎛 BOTONES
# =============================
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    chat_id = query.message.chat.id

    if query.data == "ver":
        txt = json.dumps(estado.get(uid, {}), indent=2)
        await context.bot.send_message(chat_id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        res = crear_workflow(estado.get(uid))
        if "ok" in res:
            await context.bot.send_message(chat_id, "✅ Creado en n8n")
        else:
            await context.bot.send_message(chat_id, f"❌ Error:\n{res['error']}")

    elif query.data == "mejorar":
        mejor = llamar_ia(f"Optimiza este workflow:\n{json.dumps(estado.get(uid))}")
        wf = limpiar_json(mejor)

        if validar(wf):
            estado[uid] = wf
            await context.bot.send_message(chat_id, "✅ Mejorado")
        else:
            await context.bot.send_message(chat_id, "❌ Falló mejora")

    elif query.data == "regen":
        await procesar(query, context, "regenerar flujo completo")

# =============================
# 📩 MENSAJES
# =============================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)

# =============================
# 🚀 START
# =============================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 ULTRA SaaS ACTIVO")
app.run_polling()
