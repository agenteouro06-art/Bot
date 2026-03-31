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

# =============================
# 🤖 IA (GENERADOR / CORRECTOR)
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
                    {
                        "role": "system",
                        "content": "Eres experto en n8n. SOLO RESPONDES JSON válido, sin texto adicional."
                    },
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30
        )
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("ERROR IA:", e)
        return None

# =============================
# 🧹 LIMPIAR JSON
# =============================
def limpiar_json(texto):
    if not texto:
        return None
    try:
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        return json.loads(texto[inicio:fin])
    except:
        return None

# =============================
# 🔍 VALIDADOR
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
# 🧬 BASE MINIMA (NO ES FLOW FIJO)
# =============================
def base_minima():
    return {
        "name": "CLAW Dynamic Flow",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200,300],
                "parameters": {
                    "path": "auto",
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
                            {"name":"status","value":"ok"}
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
# 🔧 NORMALIZAR
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
# 🧠 GENERAR + CORREGIR IA
# =============================
def generar_workflow(texto):

    # 1. GENERAR
    raw = llamar_ia(f"""
Crea un workflow COMPLETO de n8n en JSON.

REQUISITOS:
- nodes reales de n8n
- connections válidas
- mínimo 3 nodos
- usar webhook como entrada

Pedido:
{texto}
""")

    wf = limpiar_json(raw)

    # 2. VALIDAR
    if validar(wf):
        return wf

    # 3. CORREGIR CON IA
    raw_fix = llamar_ia(f"""
Corrige este JSON de n8n para que sea válido:

{raw}

Devuelve SOLO JSON válido.
""")

    wf_fix = limpiar_json(raw_fix)

    if validar(wf_fix):
        return wf_fix

    # 4. FALLBACK DINÁMICO (NO FIJO)
    return base_minima()

# =============================
# 🤖 MOTOR
# =============================
async def procesar(update, context, texto):
    uid = update.effective_user.id

    pasos = [
        "🧠 ANALISTA IA real...",
        "🏗 ARQUITECTO IA...",
        "🎨 GENERANDO FLOW...",
        "🔍 VALIDANDO...",
        "⚙ CORRIGIENDO...",
        "💰 OPTIMIZANDO..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.3)

    wf = generar_workflow(texto)

    estado[uid] = wf

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
        "💀 FLOW generado dinámicamente",
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
        wf = generar_workflow(json.dumps(estado.get(uid)))
        estado[uid] = wf
        await context.bot.send_message(chat_id, "🧠 Mejorado con IA")

    elif query.data == "regen":
        await procesar(query, context, "crear workflow avanzado")

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

print("🔥 CLAW IA DINÁMICA ACTIVA")
app.run_polling()
