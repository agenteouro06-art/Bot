import os, json, requests, traceback
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, CallbackQueryHandler, filters
)

# =========================
# 🔐 CARGAR ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER   = int(os.getenv("ALLOWED_USER", "0"))
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

print("TOKEN:", TELEGRAM_TOKEN)
print("USER:", ALLOWED_USER)
print("OPENROUTER:", "OK" if OPENROUTER_KEY else "MISSING")

# =========================
# 🤖 OPENROUTER
# =========================
def or_chat(system, user, max_tokens=2000):
    try:
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

        r = requests.post(url, headers=headers, json=data, timeout=30)

        print("🧠 RAW IA:", r.text[:500])

        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        print("❌ ERROR IA:", e)
        return '{"error":"fail"}'


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
# 🧬 PLANTILLA BASE
# =========================
def flujo_base():
    return {
        "name": "Flujo Base",
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
                "name": "Respuesta",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [450, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "msg", "value": "ok"}
                        ]
                    }
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Respuesta", "type": "main", "index": 0}]]
            }
        },
        "settings": {},
        "pinData": {}
    }


# =========================
# 🤖 GENERAR FLUJO
# =========================
def generar_flujo(desc):
    print("🧠 Generando flujo...")

    base = flujo_base()

    system = """
Eres experto en n8n.
Modifica el workflow base según el requerimiento.

Devuelve SOLO JSON válido.
"""

    prompt = f"""
BASE:
{json.dumps(base)}

REQUERIMIENTO:
{desc}
"""

    raw = or_chat(system, prompt)

    try:
        limpio = limpiar_json(raw)
        data = json.loads(limpio)

        print("✅ JSON OK")
        return data

    except Exception as e:
        print("❌ JSON ERROR:", e)
        print("RAW:", raw)

        return base


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
        print("📩 Mensaje de:", uid)

        if uid != ALLOWED_USER:
            print("❌ Usuario no autorizado")
            return

        texto = update.message.text
        chat  = update.effective_chat.id

        await ctx.bot.send_message(chat, "🧠 Procesando...")

        flujo = generar_flujo(texto)

        st = get_st(uid)
        st["flujo"] = flujo

        kb = [[InlineKeyboardButton("📄 Ver JSON", callback_data="json")]]

        await ctx.bot.send_message(
            chat,
            f"✅ Flujo generado:\n{flujo.get('name','sin nombre')}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    except Exception as e:
        print("❌ ERROR HANDLE:", e)
        traceback.print_exc()


# =========================
# 🔘 BOTONES
# =========================
async def botones(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        q = update.callback_query
        await q.answer()

        uid = q.from_user.id
        st = get_st(uid)

        if q.data == "json":
            txt = json.dumps(st["flujo"], indent=2)

            for i in range(0, len(txt), 3500):
                await q.message.reply_text(
                    f"```json\n{txt[i:i+3500]}\n```",
                    parse_mode="Markdown"
                )

    except Exception as e:
        print("❌ ERROR BOTONES:", e)


# =========================
# 🚀 START
# =========================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 BOT ACTIVO - ENV OK")


# =========================
# 🧠 MAIN
# =========================
def main():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN no cargado")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CallbackQueryHandler(botones))

    print("🚀 BOT CORRIENDO...")
    app.run_polling()


if __name__ == "__main__":
    main()
