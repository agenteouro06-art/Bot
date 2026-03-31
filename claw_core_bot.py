import os, json, requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, CallbackQueryHandler, filters
)

# =========================
# 🔐 ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER   = int(os.getenv("ALLOWED_USER", "0"))
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

# =========================
# 🤖 OPENROUTER
# =========================
def or_chat(system, user, max_tokens=2000):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "anthropic/claude-3-haiku",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "max_tokens": max_tokens
    }

    r = requests.post(url, headers=headers, json=data)

    try:
        return r.json()["choices"][0]["message"]["content"]
    except:
        print("ERROR OPENROUTER:", r.text)
        return '{"error":"fail"}'

# =========================
# 🧹 LIMPIAR JSON
# =========================
def limpiar_json(raw):
    if "```" in raw:
        raw = raw.split("```")[1]

    raw = raw.replace("json", "").strip()

    inicio = raw.find("{")
    fin = raw.rfind("}") + 1

    return raw[inicio:fin]

# =========================
# 🧬 PLANTILLAS
# =========================
PLANTILLAS = {
    "pedido": {
        "name": "Pedidos WhatsApp",
        "nodes": [
            {"id":"1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[200,300],"parameters":{"path":"pedido","httpMethod":"POST"}},
            {"id":"2","name":"Set Pedido","type":"n8n-nodes-base.set","typeVersion":2,"position":[450,300],"parameters":{"values":{"string":[{"name":"pedido","value":"={{$json.body}}"}]}}},
            {"id":"3","name":"Google Sheets","type":"n8n-nodes-base.googleSheets","typeVersion":4,"position":[700,300],"parameters":{"operation":"append"}}
        ],
        "connections":{
            "Webhook":{"main":[[{"node":"Set Pedido","type":"main","index":0}]]},
            "Set Pedido":{"main":[[{"node":"Google Sheets","type":"main","index":0}]]}
        },
        "settings":{},
        "pinData":{}
    }
}

def elegir_base(desc):
    d = desc.lower()
    if "pedido" in d or "restaurante" in d:
        return PLANTILLAS["pedido"]
    return list(PLANTILLAS.values())[0]

# =========================
# 🤖 GENERADOR
# =========================
def generar_flujo(desc):
    base = elegir_base(desc)

    system = """
Eres experto en n8n.

MODIFICA el workflow base según el requerimiento.

Devuelve SOLO JSON válido.
"""

    prompt = f"""
BASE:
{json.dumps(base, indent=2)}

REQUERIMIENTO:
{desc}
"""

    raw = or_chat(system, prompt)

    try:
        limpio = limpiar_json(raw)
        data = json.loads(limpio)
        return data
    except:
        return base

# =========================
# 💬 TELEGRAM
# =========================
estado = {}

def get_st(uid):
    if uid not in estado:
        estado[uid] = {"flujo": None}
    return estado[uid]

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ALLOWED_USER:
        return

    texto = update.message.text
    st = get_st(uid)

    await update.message.reply_text("🧠 Creando flujo real...")

    flujo = generar_flujo(texto)

    st["flujo"] = flujo

    kb = [
        [InlineKeyboardButton("📄 Ver JSON", callback_data="json")]
    ]

    await update.message.reply_text(
        f"✅ Flujo generado: {flujo.get('name','sin nombre')}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def botones(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    st = get_st(uid)

    if q.data == "json":
        txt = json.dumps(st["flujo"], indent=2)

        for i in range(0, len(txt), 3500):
            await q.message.reply_text(f"```json\n{txt[i:i+3500]}\n```", parse_mode="Markdown")

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 CLAW DIOS ACTIVO")

# =========================
# 🚀 RUN
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 BOT ACTIVO")
app.run_polling()
