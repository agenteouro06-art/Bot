import os
import json
import asyncio
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# =========================
# 🔐 ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

estado = {}

# =========================
# 🤖 OPENROUTER SIN SDK
# =========================
def ia_generar_flujo(prompt):

    system = """
Eres experto en n8n.

Devuelve SOLO JSON válido.

REGLAS:
- SOLO JSON
- root: name, nodes, connections, settings
- SIN id, SIN versionId
- nodes: name, type, typeVersion, position, parameters
- position: [x,y]
- conexiones válidas

Usa nodos como:
- webhook
- httpRequest
- function
- set
- if
- respondToWebhook

"""

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "anthropic/claude-3-haiku",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ]
        }
    )

    data = r.json()

    texto = data["choices"][0]["message"]["content"]

    if "```" in texto:
        texto = texto.split("```")[1]
        texto = texto.replace("json", "").strip()

    return json.loads(texto)

# =========================
# 🧹 LIMPIADOR PRO
# =========================
def limpiar_workflow(wf):

    limpio = {
        "name": wf.get("name", "CLAW Flow"),
        "nodes": [],
        "connections": {},
        "settings": {}
    }

    for i, n in enumerate(wf.get("nodes", [])):
        limpio["nodes"].append({
            "name": n["name"],
            "type": n["type"],
            "typeVersion": n.get("typeVersion", 1),
            "position": [200 + i*250, 300],
            "parameters": n.get("parameters", {})
        })

    # reconstruir conexiones
    nodes = limpio["nodes"]
    for i in range(len(nodes)-1):
        limpio["connections"][nodes[i]["name"]] = {
            "main": [[{
                "node": nodes[i+1]["name"],
                "type": "main",
                "index": 0
            }]]
        }

    return limpio

# =========================
# 🔁 CREACIÓN CON AUTO-FIX
# =========================
def crear_n8n(wf):

    for intento in range(3):

        print(f"🚀 Intento {intento+1}")

        payload = limpiar_workflow(wf)

        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=payload
        )

        print("STATUS:", r.status_code)
        print("RESP:", r.text)

        if r.status_code in [200, 201]:
            return r.json()

        # 🔥 auto-fix si settings falta
        if "settings" in r.text:
            payload["settings"] = {}

    return {"error": "❌ Falló después de 3 intentos"}

# =========================
# 🧠 DETECTOR DE REQUISITOS
# =========================
def detectar_requisitos(texto):

    req = []

    t = texto.lower()

    if "whatsapp" in t:
        req.append("API WhatsApp (Twilio o Meta)")

    if "correo" in t or "gmail" in t:
        req.append("Credenciales IMAP o Gmail")

    if "captura" in t or "imagen" in t:
        req.append("OCR (Google Vision / AWS Textract)")

    if "banco" in t:
        req.append("Acceso a correos del banco")

    return req

# =========================
# 🤖 MOTOR
# =========================
async def procesar(update, context, texto):

    uid = update.effective_user.id

    pasos = [
        "🧠 Analizando...",
        "🏗 Diseñando...",
        "⚙ Generando...",
        "🧹 Corrigiendo...",
        "🚀 Listo..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.2)

    try:
        wf = ia_generar_flujo(texto)
    except Exception as e:
        await update.message.reply_text(f"❌ Error IA: {e}")
        return

    estado[uid] = wf

    reqs = detectar_requisitos(texto)

    req_txt = "\n".join([f"• {r}" for r in reqs]) if reqs else "• Ninguno"

    kb = [
        [
            InlineKeyboardButton("🚀 Crear", callback_data="crear"),
            InlineKeyboardButton("📄 JSON", callback_data="ver")
        ]
    ]

    await update.message.reply_text(
        f"✅ Flujo listo\n\n🔧 Configurar:\n{req_txt}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# =========================
# 🎛 BOTONES
# =========================
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    chat = query.message.chat.id

    if query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await context.bot.send_message(chat, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        await context.bot.send_message(chat, "🚀 Enviando a n8n...")
        res = crear_n8n(estado[uid])
        await context.bot.send_message(chat, str(res))

# =========================
# 📩 MENSAJES
# =========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)

# =========================
# 🚀 START
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW SERVER ESTABLE ACTIVO")
app.run_polling()
