import requests, asyncio, os, re, json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ========================
# CONFIG
# ========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

# ========================
# UTILIDADES INTELIGENTES
# ========================

def is_real_command(cmd):
    return any(x in cmd for x in ["apt", "docker", "systemctl", "pip", "python"])

def needs_ocr(text):
    palabras = ["imagen", "foto", "captura", "pantalla", "screenshot"]
    return any(p in text for p in palabras)

def detect_tools(text):
    tools = []

    if "whatsapp" in text:
        tools.append("whatsapp")

    if "correo" in text or "gmail" in text:
        tools.append("gmail")

    if needs_ocr(text):
        tools.append("ocr")

    return tools

# ========================
# TEST CONEXIÓN N8N
# ========================
def test_n8n():
    try:
        r = requests.get(f"{N8N_URL}/api/v1/workflows", headers={
            "X-N8N-API-KEY": N8N_API_KEY
        }, timeout=5)
        return r.status_code == 200
    except:
        return False

# ========================
# CREAR WORKFLOW PRO REAL
# ========================
def create_workflow(text):

    tools = detect_tools(text)
    nodes = []
    connections = {}

    # Webhook base
    nodes.append({
        "parameters": {
            "path": "auto-webhook",
            "httpMethod": "POST"
        },
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1,
        "position": [200, 300]
    })

    last = "Webhook"

    # OCR si aplica
    if "ocr" in tools:
        nodes.append({
            "parameters": {
                "url": "https://api.ocr.space/parse/image",
                "method": "POST"
            },
            "name": "OCR",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 1,
            "position": [400, 300]
        })
        connections[last] = {"main": [[{"node": "OCR"}]]}
        last = "OCR"

    # Extraer datos
    nodes.append({
        "parameters": {
            "functionCode": """
const text = JSON.stringify($json);
const ref = text.match(/\\d{6,}/);
return [{ref: ref ? ref[0] : null}];
"""
        },
        "name": "Procesar Datos",
        "type": "n8n-nodes-base.function",
        "typeVersion": 1,
        "position": [600, 300]
    })
    connections[last] = {"main": [[{"node": "Procesar Datos"}]]}
    last = "Procesar Datos"

    # Gmail si aplica
    if "gmail" in tools:
        nodes.append({
            "parameters": {
                "resource": "message",
                "operation": "getAll"
            },
            "name": "Gmail",
            "type": "n8n-nodes-base.gmail",
            "typeVersion": 1,
            "position": [800, 300]
        })
        connections[last] = {"main": [[{"node": "Gmail"}]]}
        last = "Gmail"

    # Validación
    nodes.append({
        "parameters": {
            "functionCode": """
const ref = $json.ref;
const data = JSON.stringify($json);
return [{ok: ref && data.includes(ref)}];
"""
        },
        "name": "Validar",
        "type": "n8n-nodes-base.function",
        "typeVersion": 1,
        "position": [1000, 300]
    })
    connections[last] = {"main": [[{"node": "Validar"}]]}

    return {
        "name": "CLAW Auto Workflow",
        "nodes": nodes,
        "connections": connections,
        "settings": {}
    }

# ========================
# ENVIAR A N8N
# ========================
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
        return r.json()
    except Exception as e:
        return str(e)

# ========================
# HANDLE
# ========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ALLOWED_USER:
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    text = update.message.text.lower()

    # ========================
    # DETECTOR WORKFLOW
    # ========================
    if "workflow" in text or "flujo" in text or "automatiza" in text:

        tools = detect_tools(text)
        context.user_data["tools"] = tools
        context.user_data["text"] = text

        kb = [[
            InlineKeyboardButton("✅ Continuar", callback_data="build"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
        ]]

        resumen = "🧠 Detecté:\n"
        for t in tools:
            resumen += f"✔ {t}\n"

        await update.message.reply_text(
            resumen + "\n¿Crear workflow?",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # ========================
    # COMANDOS
    # ========================
    cmd = None

    if "docker" in text:
        cmd = "apt-get update && apt-get install -y docker.io"

    if cmd and is_real_command(cmd):

        context.user_data["pending_cmd"] = cmd

        kb = [[
            InlineKeyboardButton("✅ Ejecutar", callback_data="yes"),
            InlineKeyboardButton("❌ Cancelar", callback_data="no")
        ]]

        await update.message.reply_text(
            f"⚠️ Ejecutar:\n{cmd}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    await update.message.reply_text("No entendí")

# ========================
# BOTONES
# ========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    data = q.data

    if data == "build":

        if not test_n8n():
            await q.edit_message_text("❌ n8n no responde")
            return

        text = context.user_data.get("text", "")
        workflow = create_workflow(text)

        res = create_n8n_workflow(workflow)

        await q.edit_message_text("🚀 Workflow creado")

        await q.message.reply_text(
            "📌 Configura:\n"
            "- Gmail (credenciales)\n"
            "- WhatsApp API\n"
            "- OCR API si aplica\n\n"
            "Luego prueba el webhook"
        )
        return

    if data == "cancel":
        await q.edit_message_text("❌ Cancelado")
        return

    if data == "yes":
        cmd = context.user_data.get("pending_cmd")
        p = await asyncio.create_subprocess_shell(cmd)
        await p.communicate()
        await q.edit_message_text("✅ Ejecutado")
        return

    if data == "no":
        await q.edit_message_text("❌ Cancelado")

# ========================
# START
# ========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(buttons))

app.run_polling()
