cat > /home/mau/claw_core/claw_core_bot.py << 'EOF'
import requests, asyncio, os, re
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# 🔐 ENV
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

CONTEXT_FILE = "/home/mau/memory/context.txt"

# 🧠 CONTEXTO
def load_system_context():
    try:
        with open(CONTEXT_FILE, "r") as f:
            return f.read()
    except:
        return "Eres CLAW."

# 🔍 EXTRAER COMANDOS
def extract_commands(text):
    cmds = re.findall(r"<(.*?)>", text)
    if cmds:
        return " && ".join(cmds)

    if "[AGENTE: EJECUTOR]" in text:
        parts = text.split("[AGENTE: EJECUTOR]")[-1].strip().split("\n")
        return parts[0].strip() if parts else None

    return None

# 🛡️ FILTRO
def is_real_command(cmd):
    return any(x in cmd for x in ["apt", "docker", "systemctl", "pip", "python", "curl", "ping"])

# 🤖 IA
async def ask_ai(msg):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={
                "model": "anthropic/claude-3-haiku",
                "messages": [
                    {"role": "system", "content": load_system_context()},
                    {"role": "user", "content": msg}
                ],
                "max_tokens": 500
            },
            timeout=15
        )
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error IA: {str(e)}"

# 🔗 N8N
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

# ⚙️ EJECUTAR
async def run_command(cmd):
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return (stdout + stderr).decode()

# 🧠 MAIN
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.effective_user.id != ALLOWED_USER:
        return

    text = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # 🔥 N8N DIRECTO (SIN IA)
    if "n8n" in text.lower() or "workflow" in text.lower():

        workflow = {
            "name": "Workflow desde CLAW",
            "nodes": [],
            "connections": {}
        }

        res = create_n8n_workflow(workflow)

        await update.message.reply_text(f"✅ Enviado a n8n:\n{res}")
        return

    # 🤖 IA
    ai_res = await ask_ai(text)
    cmd = extract_commands(ai_res)

    if cmd and is_real_command(cmd):
        context.user_data["pending_cmd"] = cmd

        kb = [[
            InlineKeyboardButton("✅ EJECUTAR", callback_data="yes"),
            InlineKeyboardButton("❌ CANCELAR", callback_data="no")
        ]]

        await update.message.reply_text(ai_res, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(ai_res)

# 🔘 BOTONES
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cmd = context.user_data.get("pending_cmd")

    if q.data == "yes" and cmd:
        await q.edit_message_text(f"⏳ Ejecutando: {cmd}")

        out = await run_command(cmd)

        if len(out) > 1000:
            path = "/tmp/output.txt"
            with open(path, "w") as f:
                f.write(out)

            await q.message.reply_document(InputFile(path))
            os.remove(path)
        else:
            await q.message.reply_text(f"✅ Resultado:\n{out}")

    else:
        await q.edit_message_text("❌ Cancelado")

    context.user_data["pending_cmd"] = None

# 🚀 START
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(buttons))

print("🚀 CLAW PRO + N8N ONLINE")
app.run_polling()
EOF
