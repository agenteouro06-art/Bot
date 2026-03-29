import requests, asyncio, os, re
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# 🔐 ENV
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

# 🧠 EXTRAER COMANDO
def extract_command(text):
    if "[AGENTE: EJECUTOR]" in text:
        return text.split("]")[-1].strip()
    return None

# 🔐 SEGURIDAD
def is_safe(cmd):
    BLOCKED = ["rm -rf","shutdown","reboot","mkfs","dd"]
    BAD = [";","&&","|"]
    return not any(x in cmd for x in BLOCKED) and not any(x in cmd for x in BAD)

# 🔥 CREAR WORKFLOW REAL
def create_n8n_workflow():
    data = {
        "name": "CLAW Workflow",
        "nodes": [
            {
                "parameters": {},
                "id": "start-node",
                "name": "Start",
                "type": "n8n-nodes-base.start",
                "typeVersion": 1,
                "position": [250, 300]
            }
        ],
        "connections": {},
        "active": False,
        "settings": {}
    }

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

# ⚡ EJECUTAR COMANDO
async def run_cmd(cmd):
    p = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    out, err = await p.communicate()
    return (out + err).decode()

# 📩 MENSAJE
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    text = update.message.text

    # 🔥 DETECTOR DIRECTO N8N
    if "n8n" in text.lower() or "workflow" in text.lower():
        res = create_n8n_workflow()
        await update.message.reply_text(f"✅ Enviado a n8n:\n{res}")
        return

    # 🔥 EJEMPLO COMANDO
    if "limpieza" in text.lower():
        cmd = "find /tmp -type f -mtime +7 -delete"

        context.user_data["pending_cmd"] = cmd

        kb = [[
            InlineKeyboardButton("✅ EJECUTAR", callback_data="yes"),
            InlineKeyboardButton("❌ CANCELAR", callback_data="no")
        ]]

        await update.message.reply_text(
            f"⚠️ Ejecutar:\n{cmd}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return  # 🔥 CLAVE PARA QUE SALGAN BOTONES

    await update.message.reply_text("Comando no reconocido")

# 🔘 BOTONES
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cmd = context.user_data.get("pending_cmd")

    if q.data == "yes" and cmd and is_safe(cmd):
        await q.edit_message_text("⏳ Ejecutando...")

        out = await run_cmd(cmd)

        await q.message.reply_text(f"✅ Resultado:\n{out[:1000]}")
    else:
        await q.edit_message_text("❌ Cancelado")

    context.user_data["pending_cmd"] = None

# 🚀 APP
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(buttons))

print("🚀 CLAW FUNCIONANDO")
app.run_polling()
