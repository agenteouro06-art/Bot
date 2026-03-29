import requests, asyncio, os, re
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# =========================
# 🔐 VARIABLES DE ENTORNO
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

# =========================
# 🔐 SEGURIDAD
# =========================
def is_safe(cmd):
    BLOCKED = ["rm -rf","shutdown","reboot","mkfs","dd"]
    BAD = [";","&&","|"]
    return not any(x in cmd for x in BLOCKED) and not any(x in cmd for x in BAD)

# =========================
# 🔥 DETECTOR COMANDOS
# =========================
def is_real_command(cmd):
    return any(x in cmd for x in ["apt", "docker", "systemctl", "pip", "python", "curl", "find"])

# =========================
# 🔥 CREAR WORKFLOW EN N8N
# =========================
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

# =========================
# ⚡ EJECUTAR COMANDO
# =========================
async def run_cmd(cmd):
    p = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    out, err = await p.communicate()
    return (out + err).decode()

# =========================
# 📩 MENSAJES
# =========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    text = update.message.text.lower()

    # 🔥 DETECTOR N8N
    if "n8n" in text or "workflow" in text:
        res = create_n8n_workflow()
        await update.message.reply_text(f"✅ Enviado a n8n:\n{res}")
        return

    # 🔥 GENERADOR DE COMANDOS (puedes ampliar)
    cmd = None

    if "docker" in text:
        cmd = "apt-get update && apt-get install -y docker.io"
    elif "curl" in text:
        cmd = "apt-get update && apt-get install -y curl"
    elif "limpieza" in text:
        cmd = "find /tmp -type f -mtime +7 -delete"

    # 🔥 BOTONES (NO EJECUTA DIRECTO)
    if cmd and is_real_command(cmd):

        context.user_data["pending_cmd"] = cmd

        kb = [[
            InlineKeyboardButton("✅ EJECUTAR", callback_data="yes"),
            InlineKeyboardButton("❌ CANCELAR", callback_data="no")
        ]]

        await update.message.reply_text(
            f"⚠️ Ejecutar:\n{cmd}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

        return  # 🔥 CLAVE

    await update.message.reply_text("No entendí o no es comando")

# =========================
# 🔘 BOTONES
# =========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cmd = context.user_data.get("pending_cmd")

    if not cmd:
        await q.edit_message_text("⚠️ No hay comando pendiente")
        return

    if q.data == "yes" and is_safe(cmd):

        await q.edit_message_text(f"⏳ Ejecutando:\n{cmd}")

        try:
            out = await run_cmd(cmd)
            await q.message.reply_text(f"✅ Resultado:\n{out[:1000]}")
        except Exception as e:
            await q.message.reply_text(str(e))

    else:
        await q.edit_message_text("❌ Cancelado")

    context.user_data["pending_cmd"] = None

# =========================
# 🚀 INICIO BOT
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(buttons))

print("🚀 CLAW FUNCIONANDO")
app.run_polling()
