import os
import json
import uuid
import requests
import subprocess
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, CallbackQueryHandler, filters

# =========================
# 🔥 ENV
# =========================

load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER   = int(os.getenv("ALLOWED_USER"))
N8N_URL        = os.getenv("N8N_URL")
N8N_API_KEY    = os.getenv("N8N_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

estado = {}

# =========================
# 🧠 OPENROUTER
# =========================

def llamar_ia(system, user_msg, max_tokens=2000):
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
                    {"role": "user", "content": user_msg}
                ],
                "max_tokens": max_tokens
            },
            timeout=30
        )
        data = r.json()

        if "error" in data:
            print("ERROR IA:", data)
            return None

        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print("ERROR IA:", e)
        return None

# =========================
# 🧠 LIMPIAR JSON IA
# =========================

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
# 🧠 SYS N8N (REGLAS PRO)
# =========================

SYS_N8N = """
Eres experto en n8n.

REGLAS CRÍTICAS:

- SOLO puedes usar estos nodos:
  - n8n-nodes-base.webhook
  - n8n-nodes-base.httpRequest
  - n8n-nodes-base.set
  - n8n-nodes-base.if
  - n8n-nodes-base.function
  - n8n-nodes-base.respondToWebhook
  - n8n-nodes-base.gmail
  - n8n-nodes-base.telegram

- PROHIBIDO inventar nodos
- PROHIBIDO usar otros nodos

- Devuelve SOLO JSON válido
- Flujo debe ser COMPLETO y FUNCIONAL
"""

# =========================
# 🧠 AGENTE GENERADOR
# =========================

def agente_generador(prompt, flujo_base=None):
    if flujo_base:
        user_msg = f"""
Adapta este workflow:

{json.dumps(flujo_base)}

Para que haga esto:
{prompt}

NO borres la estructura
Devuelve JSON limpio
"""
    else:
        user_msg = f"""
Crea un workflow n8n completo para:

{prompt}

Debe tener webhook, procesamiento y respuesta
"""

    raw = llamar_ia(SYS_N8N, user_msg)
    wf = limpiar_json_ia(raw)

    if not wf or not wf.get("nodes"):
        print("❌ IA falló")
        return None

    return wf

# =========================
# 🧠 VALIDADOR
# =========================

def agente_validador(wf):
    if not wf or "nodes" not in wf:
        return None
    return wf

# =========================
# 🧠 AUTO FIX (ANTI ERROR 400)
# =========================

def agente_autofix(wf):
    limpio = {
        "name": wf.get("name", "Workflow"),
        "nodes": [],
        "connections": wf.get("connections", {}),
        "settings": {}
    }

    for n in wf.get("nodes", []):
        limpio["nodes"].append({
            "id": str(uuid.uuid4()),
            "name": n.get("name", "Nodo"),
            "type": n.get("type"),
            "typeVersion": 1,
            "position": n.get("position", [300,300]),
            "parameters": n.get("parameters", {})
        })

    return limpio

# =========================
# 🧠 N8N API
# =========================

def hdrs():
    return {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }

def n8n_listar():
    try:
        r = requests.get(f"{N8N_URL}/api/v1/workflows", headers=hdrs())
        return r.json().get("data", [])
    except:
        return []

def n8n_get(wid):
    try:
        r = requests.get(f"{N8N_URL}/api/v1/workflows/{wid}", headers=hdrs())
        return r.json()
    except:
        return None

# =========================
# 🧠 CLONADOR INTELIGENTE
# =========================

def buscar_flujo_similar(prompt):
    flujos = n8n_listar()

    mejor = None
    mejor_score = 0

    for f in flujos:
        nombre = f.get("name","").lower()
        score = sum(1 for w in prompt.lower().split() if w in nombre)

        if score > mejor_score:
            mejor_score = score
            mejor = f

    if mejor:
        print("🧠 Usando plantilla:", mejor["name"])
        return n8n_get(mejor["id"])

    return None

# =========================
# 🧠 MODO AUTÓNOMO TOTAL
# =========================

def modo_autonomo(prompt):
    print("🧠 MODO AUTÓNOMO TOTAL")

    base = buscar_flujo_similar(prompt)

    wf = agente_generador(prompt, base)

    if not wf:
        return None

    wf = agente_validador(wf)
    wf = agente_autofix(wf)

    return wf

# =========================
# 🚀 CREAR EN N8N
# =========================

def crear(workflow):
    if not workflow:
        print("❌ Flujo inválido")
        return {"error": "flujo vacío"}

    r = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        headers=hdrs(),
        json=workflow
    )

    print("STATUS:", r.status_code)
    print("RESP:", r.text[:300])

    return r.json()

# =========================
# 🤖 BOT
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    texto = update.message.text
    chat  = update.effective_chat.id

    await update.message.reply_text("🧠 Generando flujo...")

    wf = modo_autonomo(texto)

    if not wf:
        await update.message.reply_text("❌ Error generando flujo")
        return

    estado[chat] = wf

    await update.message.reply_text(
        f"🔥 Flujo listo:\n{wf.get('name')}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Crear en n8n", callback_data="crear")]
        ])
    )

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    chat = q.message.chat.id

    if q.data == "crear":
        wf = estado.get(chat)

        res = crear(wf)

        await context.bot.send_message(
            chat,
            f"✅ Creado:\n{res.get('id')}"
        )

# =========================
# 🚀 START
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 BOT ACTIVO (GIFHUD READY)")
app.run_polling()
