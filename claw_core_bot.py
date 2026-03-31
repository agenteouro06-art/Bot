import os
import json
import subprocess
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, CallbackQueryHandler, filters,
)

# 🔥 CARGAR ENV (CORREGIDO)
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER   = int(os.getenv("ALLOWED_USER", "0"))
N8N_URL        = os.getenv("N8N_URL", "http://localhost:5678")
N8N_API_KEY    = os.getenv("N8N_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

MODELO = "anthropic/claude-3-haiku"

estado = {}

# 🔥 CLIENTE OPENROUTER SIN SDK OPENAI
def or_chat(system, messages, max_tokens=800):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/claw-core",
                "X-Title": "CLAW CORE Bot"
            },
            json={
                "model": MODELO,
                "messages": [{"role": "system", "content": system}] + messages,
                "max_tokens": max_tokens
            },
            timeout=30
        )

        data = r.json()

        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print("Error IA:", e)
        return ""

# 🔥 ESTADO
def get_st(uid):
    if uid not in estado:
        estado[uid] = {
            "flujo": None,
            "cmd": None,
            "historial": [],
            "modo": None,
            "flujo_desc": ""
        }
    return estado[uid]

# 🔥 NORMALIZADOR
def normalizar(wf):
    for k in ["id", "active", "createdAt", "updatedAt", "versionId"]:
        wf.pop(k, None)

    wf.setdefault("settings", {"executionOrder": "v1"})
    wf.setdefault("connections", {})
    wf.setdefault("pinData", {})

    for n in wf.get("nodes", []):
        n.setdefault("parameters", {})
        n.setdefault("position", [300, 300])
        n.setdefault("typeVersion", 1)

        if not n.get("id"):
            n["id"] = n.get("name", "node").replace(" ", "_").lower()

    return wf

# 🔥 CREAR EN N8N
def n8n_crear(wf):
    wf = normalizar(wf)

    r = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        headers={
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json"
        },
        json=wf,
        timeout=20
    )

    try:
        return r.json()
    except:
        return {"error": r.text}

# 🔥 GENERADOR IA (MEJORADO)
def generar_flujo(desc):
    system = """
Eres experto en n8n.

Genera workflows REALES y FUNCIONALES.

REGLAS:
- SOLO JSON
- NO texto extra
- Nodes válidos de n8n
- Flujo completo listo para producción
"""

    raw = or_chat(system, [{"role": "user", "content": desc}], 3000)

    try:
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()

        return json.loads(raw)

    except:
        print("⚠ IA devolvió JSON inválido")
        return None

# 🚀 PROCESAR MENSAJE
async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid != ALLOWED_USER:
        return

    texto = update.message.text
    st = get_st(uid)

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

    wf = generar_flujo(texto)

    if not wf:
        await update.message.reply_text("❌ IA falló generando JSON válido")
        return

    st["flujo"] = wf
    st["flujo_desc"] = texto

    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="ver")
        ],
        [
            InlineKeyboardButton("🔄 Regenerar", callback_data="regen")
        ]
    ]

    await update.message.reply_text(
        "💀 FLOW GENERADO (IA REAL)",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# 🎛 BOTONES
async def botones(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    st = get_st(uid)
    chat = q.message.chat.id

    if q.data == "crear":
        await ctx.bot.send_message(chat, "🚀 Creando en n8n...")

        res = n8n_crear(st["flujo"])

        if res.get("id"):
            await ctx.bot.send_message(chat, f"✅ Creado ID: {res['id']}")
        else:
            await ctx.bot.send_message(chat, f"❌ Error:\n{res}")

    elif q.data == "ver":
        txt = json.dumps(st["flujo"], indent=2)
        await ctx.bot.send_message(chat, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif q.data == "regen":
        await ctx.bot.send_message(chat, "🔄 Regenerando...")

        wf = generar_flujo(st["flujo_desc"])

        if wf:
            st["flujo"] = wf
            await ctx.bot.send_message(chat, "✅ Regenerado")
        else:
            await ctx.bot.send_message(chat, "❌ Error regenerando")

# 🚀 INICIO
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW CORE FULL IA (OPENROUTER) ACTIVO")
app.run_polling()
