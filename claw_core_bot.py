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
# 🔥 CREAR WORKFLOW EN N8N
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
# 🧠 GENERADOR WORKFLOW REAL
# =========================
def generate_workflow_whatsapp_banco():

    return {
        "name": "Validación Pagos WhatsApp vs Banco",
        "nodes": [
            {
                "parameters": {
                    "path": "whatsapp-pagos",
                    "httpMethod": "POST"
                },
                "id": "webhook",
                "name": "Webhook WhatsApp",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [200, 300]
            },
            {
                "parameters": {
                    "operation": "readBinaryData"
                },
                "id": "ocr",
                "name": "Leer Imagen (OCR)",
                "type": "n8n-nodes-base.readBinaryFile",
                "typeVersion": 1,
                "position": [400, 300]
            },
            {
                "parameters": {
                    "resource": "message",
                    "operation": "getAll"
                },
                "id": "gmail",
                "name": "Leer Correos Banco",
                "type": "n8n-nodes-base.gmail",
                "typeVersion": 1,
                "position": [600, 300]
            },
            {
                "parameters": {
                    "functionCode": """
const refImg = $json["reference"];
const refMail = $json["subject"];

if(refImg && refMail && refMail.includes(refImg)){
  return [{match:true}];
}
return [{match:false}];
"""
                },
                "id": "validar",
                "name": "Validar Pago",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [800, 300]
            }
        ],
        "connections": {
            "Webhook WhatsApp": {
                "main": [[{"node": "Leer Imagen (OCR)", "type": "main", "index": 0}]]
            },
            "Leer Imagen (OCR)": {
                "main": [[{"node": "Leer Correos Banco", "type": "main", "index": 0}]]
            },
            "Leer Correos Banco": {
                "main": [[{"node": "Validar Pago", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }

# =========================
# 📩 MENSAJES
# =========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    text = update.message.text.lower()

    # 🔥 DETECTOR INTELIGENTE
    if "whatsapp" in text and "banco" in text:

        workflow = generate_workflow_whatsapp_banco()

        context.user_data["workflow"] = workflow

        explicacion = """
[AGENTE: ARQUITECTO]
Se detecta necesidad de validación automática de pagos.

[AGENTE: DISEÑADOR]
Se crea flujo:
- Webhook recibe captura WhatsApp
- OCR extrae datos
- Gmail lee correo banco
- Se comparan referencias

[AGENTE: VALIDADOR]
Se valida coincidencia de pago.

[AGENTE: RESULTADO]
Si coincide → marcar como validado.
"""

        kb = [[
            InlineKeyboardButton("✅ CREAR EN N8N", callback_data="crear"),
            InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")
        ]]

        await update.message.reply_text(explicacion, reply_markup=InlineKeyboardMarkup(kb))
        return

    await update.message.reply_text("No entendí la solicitud")

# =========================
# 🔘 BOTONES
# =========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    workflow = context.user_data.get("workflow")

    if q.data == "crear" and workflow:

        await q.edit_message_text("⏳ Creando workflow en n8n...")

        res = create_n8n_workflow(workflow)

        await q.message.reply_text(f"✅ Workflow creado:\n{res}")

    else:
        await q.edit_message_text("❌ Cancelado")

# =========================
# 🚀 BOT
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(buttons))

print("🚀 CLAW NIVEL PRO ACTIVO")
app.run_polling()
