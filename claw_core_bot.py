import os, json, subprocess, requests
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, CallbackQueryHandler, filters,
)

# ✅ CORREGIDO: comillas normales
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER   = int(os.getenv("ALLOWED_USER", "0"))
N8N_URL        = os.getenv("N8N_URL", "http://localhost:5678")
N8N_API_KEY    = os.getenv("N8N_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

MODELO = "anthropic/claude-3-haiku"

# ✅ CORREGIDO OpenRouter
client = OpenAI(
    api_key=OPENROUTER_KEY,
    base_url="https://openrouter.ai/api/v1",
)

estado = {}

def get_st(uid):
    if uid not in estado:
        estado[uid] = {
            "flujo": None,
            "cmd": None,
            "historial": [],
            "repair_id": None,
            "flujo_desc": "",
            "repair_desc": "",
            "modo": None,
        }
    return estado[uid]

# ================================
# 🧠 IA CHAT
# ================================
def or_chat(system, messages, max_tokens=600):
    msgs = [{"role": "system", "content": system}] + messages

    r = client.chat.completions.create(
        model=MODELO,
        max_tokens=max_tokens,
        messages=msgs,
        extra_headers={
            "HTTP-Referer": "https://github.com/claw-core",
            "X-Title": "CLAW CORE Bot",
        },
    )

    return r.choices[0].message.content.strip()

# ================================
# 🧠 CLASIFICADOR
# ================================
SYS_CLAS = """Clasifica el mensaje. Responde SOLO JSON valido.
{"tipo":"","resumen":"","datos":{}}
Tipos:
FLUJO_CREAR
FLUJO_REPARAR
FLUJO_LISTAR
CMD_SISTEMA
PREGUNTA
OTRO
"""

def clasificar(texto):
    try:
        raw = or_chat(SYS_CLAS, [{"role": "user", "content": texto}], max_tokens=200)

        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()

        return json.loads(raw)

    except Exception as e:
        print(f"[clasificar error] {e}")
        return {"tipo": "OTRO", "datos": {}}

# ================================
# 🧠 GENERADOR N8N
# ================================
SYS_N8N = """Eres experto en n8n.
Devuelve SOLO JSON valido de workflow completo."""

def generar_flujo(descripcion, flujo_base=None):
    try:
        if flujo_base:
            prompt = f"Repara este flujo:\n{json.dumps(flujo_base)}\nProblema:{descripcion}"
        else:
            prompt = f"Crea workflow n8n:\n{descripcion}"

        raw = or_chat(SYS_N8N, [{"role": "user", "content": prompt}], max_tokens=4000)

        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()

        return json.loads(raw)

    except Exception as e:
        print("Error IA:", e)
        return None

# ================================
# 🧠 N8N API
# ================================
def hdrs():
    return {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }

def normalizar(wf):
    if not wf:
        return None

    wf.pop("id", None)
    wf.pop("active", None)

    wf.setdefault("settings", {"executionOrder": "v1"})
    wf.setdefault("connections", {})
    wf.setdefault("nodes", [])

    for n in wf["nodes"]:
        n.setdefault("parameters", {})
        n.setdefault("position", [300, 300])
        n.setdefault("typeVersion", 1)

    return wf

def n8n_crear(wf):
    wf = normalizar(wf)

    r = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        headers=hdrs(),
        json=wf,
        timeout=20
    )

    try:
        return r.json()
    except:
        return {"error": r.text}

# ================================
# 🤖 BOT
# ================================
async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text
    uid = update.effective_user.id
    st = get_st(uid)

    await ctx.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    intent = clasificar(texto)
    tipo = intent.get("tipo")

    # 🔥 CREAR FLUJO
    if tipo == "FLUJO_CREAR":
        await update.message.reply_text("🧠 Generando workflow...")

        wf = generar_flujo(texto)

        if not wf:
            await update.message.reply_text("❌ IA falló generando JSON")
            return

        st["flujo"] = wf

        kb = [
            [InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear")],
            [InlineKeyboardButton("📄 Ver JSON", callback_data="ver")]
        ]

        await update.message.reply_text(
            f"✅ Flujo generado: {wf.get('name', 'sin nombre')}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    else:
        await update.message.reply_text("🤖 No entendí, intenta otra vez")

# ================================
# 🎛 BOTONES
# ================================
async def botones(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    st = get_st(uid)

    if q.data == "crear":
        res = n8n_crear(st["flujo"])

        if res.get("id"):
            await q.message.reply_text(f"✅ Creado en n8n ID: {res['id']}")
        else:
            await q.message.reply_text(f"❌ Error: {res}")

    elif q.data == "ver":
        txt = json.dumps(st["flujo"], indent=2)

        for i in range(0, len(txt), 4000):
            await q.message.reply_text(f"```json\n{txt[i:i+4000]}\n```", parse_mode="Markdown")

# ================================
# 🚀 START
# ================================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 BOT FUNCIONANDO")
app.run_polling()
