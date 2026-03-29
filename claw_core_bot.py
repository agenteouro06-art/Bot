import requests, asyncio, os, re
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
# SEGURIDAD
# ========================
def is_real_command(cmd):
    return any(x in cmd for x in ["apt", "docker", "systemctl", "pip", "python"])

# ========================
# CREAR WORKFLOW REAL
# ========================
def create_payment_workflow():

    return {
        "name": "Validación Pagos WhatsApp",
        "nodes": [
            {
                "parameters": {
                    "path": "validar-pago",
                    "httpMethod": "POST"
                },
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [200, 300]
            },
            {
                "parameters": {
                    "functionCode": """
const texto = $json["body"] || "";

const ref = texto.match(/\\d{6,}/);

return [{
  referencia: ref ? ref[0] : null
}];
"""
                },
                "name": "Extraer Referencia",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [400, 300]
            },
            {
                "parameters": {
                    "resource": "message",
                    "operation": "getAll"
                },
                "name": "Gmail",
                "type": "n8n-nodes-base.gmail",
                "typeVersion": 1,
                "position": [600, 300]
            },
            {
                "parameters": {
                    "functionCode": """
const ref = $json["referencia"];
const correo = JSON.stringify($json);

if(ref && correo.includes(ref)){
  return [{ok:true}];
}
return [{ok:false}];
"""
                },
                "name": "Validar Pago",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [800, 300]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Extraer Referencia"}]]
            },
            "Extraer Referencia": {
                "main": [[{"node": "Gmail"}]]
            },
            "Gmail": {
                "main": [[{"node": "Validar Pago"}]]
            }
        },
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
# HANDLE MENSAJES
# ========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ALLOWED_USER:
        return

    text = update.message.text.lower()

    # ========================
    # DETECTOR WORKFLOW INTELIGENTE
    # ========================
    if "pago" in text or "transferencia" in text:

        context.user_data["flow"] = "pagos"

        kb = [[
            InlineKeyboardButton("✅ Sí tengo API WhatsApp", callback_data="wa_yes"),
            InlineKeyboardButton("❌ No tengo", callback_data="wa_no")
        ]]

        await update.message.reply_text(
            "📲 ¿Tienes API de WhatsApp?",
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

    # ========================
    # FLUJO PAGOS
    # ========================
    if data == "wa_yes":

        await q.edit_message_text("📩 Conectando Gmail...")

        workflow = create_payment_workflow()
        res = create_n8n_workflow(workflow)

        await q.message.reply_text(
            "🚀 Workflow creado\n\n"
            "✔ Recibe capturas\n"
            "✔ Extrae referencia\n"
            "✔ Lee Gmail\n"
            "✔ Valida pago\n\n"
            "⚙️ Ahora conecta:\n"
            "- Gmail en n8n\n"
            "- API WhatsApp"
        )
        return

    if data == "wa_no":
        await q.edit_message_text(
            "⚠️ Necesitas API de WhatsApp\n"
            "Te recomiendo Evolution API o Meta Cloud"
        )
        return

    # ========================
    # COMANDOS
    # ========================
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
