import os
import json
import random
import uuid
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, CallbackQueryHandler, filters
)

# =========================
# 🔥 ENV
# =========================

load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER   = int(os.getenv("ALLOWED_USER"))
N8N_URL        = os.getenv("N8N_URL")
N8N_API_KEY    = os.getenv("N8N_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    print("❌ ERROR: OPENROUTER_API_KEY no cargada")
    exit()

print("✅ OPENROUTER OK")

estado = {}

# =========================
# 🧠 BASE
# =========================

def generar_flujo_base():
    return {
        "name": f"Workflow Base {random.randint(100,999)}",
        "nodes": [],
        "connections": {},
        "settings": {}
    }

# =========================
# 🧠 OPENROUTER
# =========================

def llamar_ia(system, user_msg, max_tokens=3000):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY.strip()}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "CLAW CORE",
            },
            json={
                "model": "anthropic/claude-3-haiku",
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
            },
            timeout=30,
        )

        data = r.json()

        if "error" in data:
            print("❌ ERROR IA:", data)
            return None

        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print("❌ ERROR IA:", e)
        return None


def limpiar_json_ia(raw):
    if not raw:
        return None
    try:
        if "```" in raw:
            raw = raw.split("```")[1]
            raw = raw.replace("json", "").strip()
        return json.loads(raw)
    except:
        return None

# =========================
# 🧬 MULTI-AGENTES
# =========================

SYS_N8N = """
Eres experto en n8n.
Devuelve SOLO JSON válido sin texto adicional.
Debe incluir: name, nodes, connections, settings
"""

def agente_generador(prompt):
    raw = llamar_ia(SYS_N8N, f"Crea flujo n8n completo:\n{prompt}")
    return limpiar_json_ia(raw)


def agente_validador(wf):
    if not wf:
        return generar_flujo_base()

    wf.setdefault("nodes", [])
    wf.setdefault("connections", {})
    wf.setdefault("settings", {})

    return wf


# 🔥 FIX DEFINITIVO N8N
def agente_autofix(wf):

    wf_limpio = {
        "name": wf.get("name", f"Workflow {random.randint(100,999)}"),
        "nodes": [],
        "connections": {},
        "settings": {}
    }

    # LIMPIAR NODOS
    for n in wf.get("nodes", []):
        nodo = {
            "id": str(uuid.uuid4()),
            "name": n.get("name", "Nodo"),
            "type": n.get("type", "n8n-nodes-base.set"),
            "typeVersion": n.get("typeVersion", 1),
            "position": n.get("position", [300, 300]),
            "parameters": n.get("parameters", {})
        }

        # SOLO credentials si es válido
        if isinstance(n.get("credentials"), dict):
            nodo["credentials"] = n["credentials"]

        wf_limpio["nodes"].append(nodo)

    # LIMPIAR CONEXIONES
    conexiones = wf.get("connections", {})

    for k, v in conexiones.items():
        if isinstance(v, dict) and "main" in v:
            wf_limpio["connections"][k] = v

    return wf_limpio


# =========================
# 🧠 MODO AUTÓNOMO
# =========================

def modo_autonomo(prompt):
    for i in range(3):
        print(f"🚀 Intento {i+1}")

        wf = agente_generador(prompt)

        if not wf:
            continue

        wf = agente_validador(wf)
        wf = agente_autofix(wf)

        if wf.get("nodes"):
            print("✅ Flujo válido")
            return wf

    print("⚠️ fallback base")
    return generar_flujo_base()

# =========================
# 🔁 N8N API
# =========================

def crear(workflow):
    r = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        headers={
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json"
        },
        json=workflow,
        timeout=15
    )

    print("STATUS:", r.status_code)
    print("RESP:", r.text[:500])

    try:
        return r.json()
    except:
        return {"error": r.text}

# =========================
# 🤖 BOT
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text
    chat  = update.effective_chat.id

    await context.bot.send_message(chat, "🧠 Modo autónomo total activado...")

    wf = modo_autonomo(texto)

    estado["wf"] = wf

    await context.bot.send_message(chat, f"🔥 Flujo listo:\n{wf.get('name')}")

    kb = [[InlineKeyboardButton("Crear en n8n", callback_data="crear")]]

    await context.bot.send_message(
        chat,
        "¿Quieres enviarlo a n8n?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "crear":
        wf = estado.get("wf")

        if not wf:
            await q.message.reply_text("❌ No hay flujo en memoria")
            return

        res = crear(wf)

        if res.get("id"):
            await q.message.reply_text(f"✅ Flujo creado:\nID: {res['id']}")
        else:
            await q.message.reply_text(f"❌ Error:\n{res}")

# =========================
# 🚀 START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 CLAW CORE PRO ACTIVO\n\n"
        "Ejemplo:\n"
        "Crea un flujo que valide pagos de WhatsApp con correo del banco"
    )

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 BOT ACTIVO (GIFHUD READY)")
app.run_polling()
