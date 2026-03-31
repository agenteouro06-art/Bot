import os, json, requests, traceback
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
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
N8N_URL        = os.getenv("N8N_URL")
N8N_API_KEY    = os.getenv("N8N_API_KEY")

# =========================
# 🤖 OPENROUTER
# =========================
def or_chat(system, user):
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
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                "max_tokens": 2000
            },
            timeout=30
        )

        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        print("❌ IA ERROR:", e)
        return None


# =========================
# 🧹 LIMPIAR JSON
# =========================
def limpiar_json(raw):
    try:
        if "```" in raw:
            raw = raw.split("```")[1]
        raw = raw.replace("json", "").strip()

        inicio = raw.find("{")
        fin = raw.rfind("}") + 1

        return raw[inicio:fin]
    except:
        return raw


# =========================
# 🧬 VALIDADOR REAL
# =========================
def validar_flujo(wf):
    if not isinstance(wf, dict):
        return False

    if "nodes" not in wf or len(wf["nodes"]) < 3:
        return False

    tipos_validos = ["webhook", "http", "google", "if", "set"]

    score = 0
    for n in wf["nodes"]:
        t = n.get("type", "").lower()
        if any(x in t for x in tipos_validos):
            score += 1

    return score >= 2


# =========================
# 🧬 GENERADOR
# =========================
def generar_flujo(desc):

    system = """
Eres experto en n8n.

Genera workflows REALES, no ejemplos.

Reglas:
- No usar nodos falsos
- Flujo funcional completo
- Conexiones correctas
- JSON limpio

Devuelve SOLO JSON.
"""

    raw = or_chat(system, desc)

    if not raw:
        return flujo_base()

    try:
        limpio = limpiar_json(raw)
        wf = json.loads(limpio)

        if validar_flujo(wf):
            return wf
        else:
            print("⚠ IA mala → fallback")

    except Exception as e:
        print("❌ JSON ERROR:", e)

    return flujo_base()


# =========================
# 🧬 BASE SEGURA
# =========================
def flujo_base():
    return {
        "name": "CLAW BASE",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "webhook",
                    "httpMethod": "POST"
                }
            },
            {
                "id": "2",
                "name": "Set",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [500, 300],
                "parameters": {
                    "values": {
                        "string": [{"name": "msg", "value": "ok"}]
                    }
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Set", "type": "main", "index": 0}]]
            }
        },
        "settings": {},
        "pinData": {}
    }


# =========================
# 🔌 N8N
# =========================
def crear_n8n(wf):
    try:
        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=wf,
            timeout=20
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# =========================
# 📦 ESTADO
# =========================
estado = {}

def get_st(uid):
    if uid not in estado:
        estado[uid] = {"flujo": None}
    return estado[uid]


# =========================
# 💬 MENSAJES
# =========================
async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = update.effective_user.id

        if uid != ALLOWED_USER:
            return

        chat = update.effective_chat.id
        texto = update.message.text

        await ctx.bot.send_chat_action(chat, ChatAction.TYPING)

        flujo = generar_flujo(texto)

        st = get_st(uid)
        st["flujo"] = flujo

        kb = [
            [
                InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
                InlineKeyboardButton("📄 Ver JSON", callback_data="json")
            ],
            [
                InlineKeyboardButton("🔄 Regenerar", callback_data="regen")
            ]
        ]

        await ctx.bot.send_message(
            chat,
            f"✅ Flujo generado:\n{flujo.get('name')}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    except Exception as e:
        traceback.print_exc()


# =========================
# 🔘 BOTONES
# =========================
async def botones(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    chat = q.message.chat.id
    st = get_st(uid)

    if q.data == "json":
        txt = json.dumps(st["flujo"], indent=2)
        for i in range(0, len(txt), 3500):
            await ctx.bot.send_message(chat, f"```json\n{txt[i:i+3500]}\n```", parse_mode="Markdown")

    elif q.data == "crear":
        await ctx.bot.send_message(chat, "🚀 Enviando a n8n...")
        res = crear_n8n(st["flujo"])
        await ctx.bot.send_message(chat, f"✅ Respuesta:\n{res}")

    elif q.data == "regen":
        await ctx.bot.send_message(chat, "🔄 Regenerando...")
        flujo = generar_flujo("flujo avanzado n8n real")
        st["flujo"] = flujo
        await ctx.bot.send_message(chat, f"♻ Nuevo flujo: {flujo.get('name')}")


# =========================
# 🚀 START
# =========================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 CLAW FULL ACTIVO")


# =========================
# 🚀 RUN
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 BOT LISTO")
app.run_polling()
