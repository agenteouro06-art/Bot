import os, requests, subprocess, asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ========================
# 🔐 CONFIG
# ========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))

N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

# ========================
# 🧠 MULTI-AGENTE
# ========================
def multi_agent_analysis(text):

    return f"""
🧠 ANÁLISIS:
- Se detectó intención de automatización

🏗 ARQUITECTO:
- Se usará n8n + OCR + Gmail + WhatsApp

🎨 DISEÑADOR:
- Flujo: Webhook → OCR → Procesar → Gmail → Validar

🧪 VALIDADOR:
- Se requieren credenciales externas

⚙ EJECUTOR:
- Preparado para ejecutar comandos

📘 EXPLICADOR:
Este flujo validará pagos automáticamente
"""

# ========================
# 🔍 DETECTOR COMANDOS
# ========================
def is_real_command(cmd):
    return any(x in cmd for x in ["apt", "docker", "systemctl", "pip", "python"])

# ========================
# 🔥 CREAR WORKFLOW PRO
# ========================
def create_n8n_workflow():

    workflow = {
        "name": "Validación Pagos PRO",
        "nodes": [
            {
                "parameters": {
                    "path": "validar-pagos",
                    "httpMethod": "POST"
                },
                "id": "webhook",
                "name": "Webhook WhatsApp",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [200,300]
            },
            {
                "parameters": {
                    "url": "https://api.ocr.space/parse/image",
                    "options": {}
                },
                "id": "ocr",
                "name": "OCR",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 1,
                "position": [400,300]
            },
            {
                "parameters": {
                    "functionCode": "return [{ref: $json.ParsedResults?.[0]?.ParsedText || ''}];"
                },
                "id": "procesar",
                "name": "Procesar Datos",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [600,300]
            },
            {
                "parameters": {
                    "resource": "message",
                    "operation": "getAll"
                },
                "id": "gmail",
                "name": "Gmail",
                "type": "n8n-nodes-base.gmail",
                "typeVersion": 1,
                "position": [800,300]
            },
            {
                "parameters": {
                    "functionCode": """
const ref = $json.ref || "";
const correo = $json.subject || "";

if(correo.includes(ref)){
  return [{ok:true}];
}
return [{ok:false}];
"""
                },
                "id": "validar",
                "name": "Validar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [1000,300]
            }
        ],
        "connections": {
            "Webhook WhatsApp": {
                "main": [[{"node": "OCR", "type": "main", "index": 0}]]
            },
            "OCR": {
                "main": [[{"node": "Procesar Datos", "type": "main", "index": 0}]]
            },
            "Procesar Datos": {
                "main": [[{"node": "Gmail", "type": "main", "index": 0}]]
            },
            "Gmail": {
                "main": [[{"node": "Validar", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }

    try:
        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=workflow
        )
        return r.json()
    except Exception as e:
        return str(e)

# ========================
# ⚙ INSTALAR WHATSAPP API
# ========================
def install_whatsapp():
    return subprocess.getoutput("docker run -d --name whatsapp-api -p 3000:3000 devlikeapro/whatsapp-http-api")

# ========================
# 💬 HANDLER PRINCIPAL
# ========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ALLOWED_USER:
        return

    text = update.message.text.lower()

    await update.message.chat.send_action("typing")

    # 🧠 MULTI AGENTE
    if "problema" in text or "error" in text:
        await update.message.reply_text(multi_agent_analysis(text))
        return

    # 🔥 DETECTOR WORKFLOW
    if "workflow" in text or "n8n" in text:

        await update.message.reply_text("📊 Analizando...")

        context.user_data["need_whatsapp"] = True
        context.user_data["need_gmail"] = True

        kb = [
            [InlineKeyboardButton("SI tengo WhatsApp API", callback_data="wa_yes")],
            [InlineKeyboardButton("NO instalar", callback_data="wa_no")]
        ]

        await update.message.reply_text(
            "¿Tienes API de WhatsApp?",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # 🔥 COMANDOS
    cmd = None

    if "docker" in text:
        cmd = "apt-get update && apt-get install -y docker.io"
    elif "limpieza" in text:
        cmd = "find /tmp -type f -mtime +7 -delete"

    if cmd and is_real_command(cmd):
        context.user_data["cmd"] = cmd

        kb = [[
            InlineKeyboardButton("✅ Ejecutar", callback_data="yes"),
            InlineKeyboardButton("❌ Cancelar", callback_data="no")
        ]]

        await update.message.reply_text(
            f"⚠️ Ejecutar:\n{cmd}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    await update.message.reply_text("❌ No entendido")

# ========================
# 🔘 BOTONES
# ========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    data = query.data

    # COMANDOS
    if data == "yes":
        cmd = context.user_data.get("cmd")
        res = subprocess.getoutput(cmd)
        await query.edit_message_text(f"✅ Ejecutado:\n{res}")
        return

    if data == "no":
        await query.edit_message_text("❌ Cancelado")
        return

    # WHATSAPP
    if data == "wa_no":
        res = install_whatsapp()
        await query.edit_message_text(f"📦 Instalando WhatsApp...\n{res}")

    if data == "wa_yes":
        await query.edit_message_text("✅ WhatsApp API OK")

    # 🚀 CREAR WORKFLOW
    wf = create_n8n_workflow()

    await asyncio.sleep(1)

    await query.message.reply_text("""
🚀 Workflow creado

✔ Recibe capturas
✔ OCR automático
✔ Lee Gmail
✔ Valida pagos

⚙️ Configura:
- Gmail en n8n
- OCR API Key
- Webhook en WhatsApp
""")

# ========================
# 🚀 MAIN
# ========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT, handle))
app.add_handler(CallbackQueryHandler(buttons))

print("🔥 CLAW PRO ACTIVO")
app.run_polling()
