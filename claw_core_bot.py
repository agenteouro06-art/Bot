import os
import json
import asyncio
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

# 🔥 IA (OPENROUTER)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

estado = {}

# =========================
# 🧠 IA CALL
# =========================
def llamar_ia(prompt):

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-3-haiku",
                "messages": [
                    {"role": "system", "content": "Eres experto en n8n. SOLO devuelves JSON válido de workflows."},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30
        )

        data = r.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        return None

# =========================
# 🧠 MULTI AGENTE REAL
# =========================

def agente_analista(texto):
    return f"""
Analiza este requerimiento y define el tipo de workflow:
{texto}
"""

def agente_arquitecto(texto):
    return f"""
Diseña un workflow n8n profesional basado en esto:
{texto}

Debe incluir:
- Webhook
- Procesamiento
- Integración real (Google Sheets, HTTP, etc)
- Respuesta final

Devuelve JSON válido de n8n.
"""

def agente_validador(json_str):
    try:
        data = json.loads(json_str)
        return data
    except:
        return None

# =========================
# 🔧 NORMALIZAR
# =========================
def normalizar(wf):
    if not wf:
        return None

    wf["name"] = wf.get("name", "CLAW AI Flow")
    wf["nodes"] = wf.get("nodes", [])
    wf["connections"] = wf.get("connections", {})
    wf["settings"] = wf.get("settings", {})

    wf.pop("id", None)
    wf.pop("active", None)

    for n in wf["nodes"]:
        n["parameters"] = n.get("parameters", {})
        n["typeVersion"] = n.get("typeVersion", 1)
        n["position"] = n.get("position", [300, 300])

    return wf

# =========================
# 🚀 CREAR N8N
# =========================
def crear_workflow(wf):

    wf = normalizar(wf)

    for intento in range(3):

        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=wf
        )

        if r.status_code == 200:
            return {"ok": True, "data": r.json()}

    return {"error": r.text}

# =========================
# 🚀 MOTOR PRO
# =========================
async def procesar(update, context, texto):

    uid = update.effective_user.id

    # 🧠 VISUAL
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
        await asyncio.sleep(0.4)

    # 🔥 ANALISTA
    analisis = llamar_ia(agente_analista(texto))

    # 🔥 ARQUITECTO
    raw = llamar_ia(agente_arquitecto(texto))

    # 🔥 VALIDAR
    wf = agente_validador(raw)

    # 🔥 FALLBACK SI IA FALLA
    if not wf:
        wf = {
            "name": "Fallback Flow",
            "nodes": [],
            "connections": {},
            "settings": {}
        }

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
        "💀 CLAW PRO IA FLOW generado",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# =========================
# 🎛 BOTONES
# =========================
async def botones(update, context):

    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    if query.data == "crear":

        await query.message.reply_text("🚀 Enviando a n8n...")

        res = crear_workflow(estado[uid])

        if "ok" in res:
            await query.message.reply_text("✅ Workflow creado correctamente")
        else:
            await query.message.reply_text(f"❌ Error:\n{res}")

    elif query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await query.message.reply_text(f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "regen":
        await query.message.reply_text("🔄 Regenerando con IA...")
        await procesar(query, context, "regenerar mejor")

    elif query.data == "mejorar":
        await query.message.reply_text("🧠 Mejorando workflow con IA...")
        mejorado = llamar_ia("Optimiza este workflow n8n:\n" + json.dumps(estado[uid]))
        wf = agente_validador(mejorado)
        if wf:
            estado[uid] = wf
            await query.message.reply_text("✅ Mejorado")
        else:
            await query.message.reply_text("❌ No se pudo mejorar")

# =========================
# 📩 MENSAJES
# =========================
async def handle(update, context):

    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)

# =========================
# 🚀 START
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW PRO IA ACTIVO")
app.run_polling()
