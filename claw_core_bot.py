import requests, asyncio, os, json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# =========================
# 🔐 ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

# =========================
# 🧠 ESTADO GLOBAL
# =========================
def init_state(context):
    if "flow" not in context.user_data:
        context.user_data["flow"] = {
            "type": None,
            "needs": [],
            "answers": {}
        }

# =========================
# 🔥 CREAR WORKFLOW
# =========================
def create_n8n_workflow(data):
    try:
        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=data,
            timeout=10
        )
        return r.text
    except Exception as e:
        return str(e)

# =========================
# 🧠 DETECTAR NECESIDADES
# =========================
def detect_needs(text):
    needs = []

    if "whatsapp" in text:
        needs.append("whatsapp")
    if "correo" in text or "gmail" in text or "banco" in text:
        needs.append("gmail")
    if "captura" in text or "imagen" in text or "ocr" in text:
        needs.append("ocr")
    if "api" in text:
        needs.append("api")

    return needs

# =========================
# 🧠 GENERAR WORKFLOW DINÁMICO
# =========================
def generate_workflow(flow_type):
    return {
        "name": f"Workflow {flow_type}",
        "nodes": [
            {
                "parameters": {"path": "webhook"},
                "id": "webhook",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [200,300]
            }
        ],
        "connections": {},
        "settings": {}
    }

# =========================
# 🧠 EXPLICACIÓN INTELIGENTE
# =========================
def explain(flow, needs):
    txt = "🧠 ANÁLISIS:\n"

    if "whatsapp" in needs:
        txt += "- Se integrará WhatsApp\n"
    if "gmail" in needs:
        txt += "- Se leerán correos\n"
    if "ocr" in needs:
        txt += "- Se procesarán imágenes\n"

    txt += "\n⚙️ Se requiere configuración.\n"

    return txt

# =========================
# 📩 MENSAJES
# =========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    init_state(context)

    text = update.message.text.lower()

    needs = detect_needs(text)

    if needs:
        context.user_data["flow"]["type"] = text
        context.user_data["flow"]["needs"] = needs

        msg = explain(text, needs)

        first = needs[0]

        kb = [[
            InlineKeyboardButton("✅ SI", callback_data=f"{first}_yes"),
            InlineKeyboardButton("❌ NO", callback_data=f"{first}_no")
        ]]

        await update.message.reply_text(msg)
        await update.message.reply_text(
            f"¿Tienes {first.upper()}?",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    await update.message.reply_text("No detecté un flujo claro")

# =========================
# 🔘 BOTONES INTELIGENTES
# =========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    state = context.user_data["flow"]
    needs = state["needs"]

    key = q.data.split("_")[0]
    val = q.data.split("_")[1]

    state["answers"][key] = val

    idx = list(state["answers"]).__len__()

    # 🔥 SIGUIENTE PREGUNTA
    if idx < len(needs):
        next_need = needs[idx]

        kb = [[
            InlineKeyboardButton("✅ SI", callback_data=f"{next_need}_yes"),
            InlineKeyboardButton("❌ NO", callback_data=f"{next_need}_no")
        ]]

        await q.edit_message_text(f"Registrado: {key} = {val}")
        await q.message.reply_text(
            f"¿Tienes {next_need.upper()}?",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # 🔥 CREAR WORKFLOW
    await q.edit_message_text("🚀 Generando workflow...")

    wf = generate_workflow(state["type"])
    res = create_n8n_workflow(wf)

    # 🔥 RESPUESTA LIMPIA
    await q.message.reply_text("✅ Workflow creado en n8n")

    resumen = "🔧 CONFIGURACIÓN:\n"

    for k,v in state["answers"].items():
        if v == "no":
            resumen += f"- Configurar {k}\n"

    await q.message.reply_text(resumen)

# =========================
# 🚀 BOT
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(buttons))

print("🚀 CLAW PRODUCCIÓN TOTAL ACTIVO")
app.run_polling()
