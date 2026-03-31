import os
import json
import asyncio
import requests
from dotenv import load_dotenv
from openai import OpenAI

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
# 🤖 IA (OPENROUTER)
# =========================
client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

MODELO = "anthropic/claude-3-haiku"

def ia_generar_flujo(prompt):

    system = """
Eres experto en n8n.

Devuelve SOLO JSON válido de un workflow IMPORTABLE en n8n.

REGLAS:
- SOLO JSON
- Campos root: name, nodes, connections, settings
- NO id, NO versionId, NO meta
- Cada nodo:
  name, type, typeVersion, position, parameters
- position = [x,y]
- Conexiones válidas
- Usa nodos reales de n8n

IMPORTANTE:
Incluye nodos necesarios para:
- Webhook o Trigger
- OCR (si hay imágenes)
- Comparación lógica
- Respuesta (HTTP o acción)

"""

    r = client.chat.completions.create(
        model=MODELO,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        max_tokens=3000
    )

    texto = r.choices[0].message.content.strip()

    # limpiar markdown si viene
    if "```" in texto:
        texto = texto.split("```")[1]
        texto = texto.replace("json", "").strip()

    return json.loads(texto)

# =========================
# 🧹 LIMPIADOR CRÍTICO
# =========================
def limpiar_workflow(wf):

    limpio = {
        "name": wf.get("name", "CLAW Flow"),
        "nodes": [],
        "connections": {},
        "settings": {}
    }

    for i, n in enumerate(wf.get("nodes", [])):
        nodo = {
            "name": n["name"],
            "type": n["type"],
            "typeVersion": n.get("typeVersion", 1),
            "position": [200 + i*250, 300],
            "parameters": n.get("parameters", {})
        }
        limpio["nodes"].append(nodo)

    # reconstruir conexiones seguras
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
# 🚀 CREAR EN N8N (RETRY REAL)
# =========================
def crear_n8n(wf):

    for intento in range(3):

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

    return {"error": "❌ No se pudo crear"}

# =========================
# 🧠 ANALISIS DE CREDENCIALES
# =========================
def detectar_requisitos(texto):

    req = []

    if "whatsapp" in texto.lower():
        req.append("WhatsApp API (Twilio o Meta)")

    if "correo" in texto.lower() or "gmail" in texto.lower():
        req.append("Credenciales Gmail / IMAP")

    if "imagen" in texto.lower() or "captura" in texto.lower():
        req.append("Servicio OCR (Google Vision / AWS Textract)")

    if "banco" in texto.lower():
        req.append("Acceso a correo bancario o API bancaria")

    return req

# =========================
# 🤖 MOTOR PRINCIPAL
# =========================
async def procesar(update, context, texto):

    uid = update.effective_user.id

    pasos = [
        "🧠 Analizando requerimiento...",
        "🔍 Diseñando flujo...",
        "⚙ Generando nodos reales...",
        "🧹 Validando JSON...",
        "🚀 Preparando despliegue..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.3)

    try:
        wf = ia_generar_flujo(texto)
    except Exception as e:
        await update.message.reply_text(f"❌ Error IA: {e}")
        return

    estado[uid] = wf

    requisitos = detectar_requisitos(texto)

    req_txt = "\n".join([f"• {r}" for r in requisitos]) if requisitos else "• Ninguno"

    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="ver")
        ]
    ]

    await update.message.reply_text(
        f"✅ Flujo generado\n\n🔧 Configuración necesaria:\n{req_txt}",
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
        await context.bot.send_message(chat, "🚀 Creando en n8n...")
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

print("💀 CLAW IA + SaaS + n8n ACTIVO")
app.run_polling()
