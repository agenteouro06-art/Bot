import os
import json
import asyncio
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# =============================
# 🔥 CONFIG
# =============================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER   = int(os.getenv("ALLOWED_USER"))
N8N_URL        = os.getenv("N8N_URL")
N8N_API_KEY    = os.getenv("N8N_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

estado = {}

# =============================
# 🤖 LLAMADA IA REAL
# =============================
def llamar_ia(prompt):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-3-haiku",
                "messages": [
                    {"role": "system", "content": "Eres experto en n8n workflows reales."},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=25
        )
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("ERROR IA:", e)
        return None

# =============================
# 🧠 AGENTES REALES
# =============================
def agente_analista(texto):
    return f"Analiza y entiende este requerimiento:\n{texto}"

def agente_arquitecto(texto):
    return f"""
Crea un workflow COMPLETO y FUNCIONAL de n8n.

REGLAS:
- SOLO JSON válido
- mínimo 4 nodos
- nodos reales de n8n
- conexiones válidas
- no texto adicional

REQUERIMIENTO:
{texto}

FORMATO:
{{
"name": "Workflow IA",
"nodes": [],
"connections": {{}},
"settings": {{}}
}}
"""

def agente_validador(json_str):
    try:
        data = json.loads(json_str)

        if "nodes" not in data or len(data["nodes"]) < 2:
            return None
        if "connections" not in data:
            return None

        return data
    except:
        return None

def agente_optimizador(workflow):
    return f"""
Optimiza este workflow de n8n.

REGLAS:
- SOLO JSON
- mejorar lógica
- mantener estructura

{json.dumps(workflow)}
"""

# =============================
# 🔥 NORMALIZAR (ANTI ERROR)
# =============================
def normalizar(workflow):
    workflow["name"] = workflow.get("name", "CLAW FLOW")
    workflow["nodes"] = workflow.get("nodes", [])
    workflow["connections"] = workflow.get("connections", {})
    workflow["settings"] = workflow.get("settings", {})

    # eliminar basura
    for k in ["id","active","versionId","meta","pinData","staticData"]:
        workflow.pop(k, None)

    for node in workflow["nodes"]:
        node["parameters"] = node.get("parameters", {})
        node["position"] = node.get("position", [300,300])
        node["typeVersion"] = node.get("typeVersion", 1)

    return workflow

# =============================
# 🚀 CREAR EN N8N (REAL)
# =============================
def crear_workflow(workflow):
    try:
        workflow = normalizar(workflow)

        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=workflow,
            timeout=20
        )

        print("RESPUESTA N8N:", r.text)

        if r.status_code != 200:
            return {"error": r.text}

        data = r.json()

        if "id" not in data:
            return {"error": "No se creó correctamente"}

        return {"ok": True, "data": data}

    except Exception as e:
        return {"error": str(e)}

# =============================
# 🧬 MOTOR MULTI-AGENTE REAL
# =============================
async def procesar(update, context, texto):
    uid = update.effective_user.id

    pasos = [
        "🧠 ANALISTA IA...",
        "🏗 ARQUITECTO IA...",
        "🎨 DISEÑADOR IA...",
        "🔍 VALIDANDO JSON...",
        "⚙ CORRIGIENDO...",
        "💰 OPTIMIZANDO..."
    ]

    for p in pasos:
        await update.message.reply_text(p)
        await asyncio.sleep(0.4)

    # 🔥 ANALIZAR
    analisis = llamar_ia(agente_analista(texto))

    # 🔥 CREAR
    raw = llamar_ia(agente_arquitecto(texto))

    print("RAW IA:", raw)

    wf = agente_validador(raw)

    if not wf:
        await update.message.reply_text("❌ IA devolvió JSON inválido")
        return

    # 🔥 OPTIMIZAR
    opt = llamar_ia(agente_optimizador(wf))
    wf_opt = agente_validador(opt)

    if wf_opt:
        wf = wf_opt

    estado[uid] = wf

    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="ver")
        ],
        [
            InlineKeyboardButton("🧠 Mejorar IA", callback_data="mejorar"),
            InlineKeyboardButton("🔄 Regenerar", callback_data="regen")
        ]
    ]

    await update.message.reply_text(
        "💀 CLAW PRO IA FLOW generado",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# =============================
# 🎛 BOTONES
# =============================
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    chat_id = query.message.chat.id

    if query.data == "ver":
        txt = json.dumps(estado.get(uid, {}), indent=2)
        await context.bot.send_message(chat_id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        await context.bot.send_message(chat_id, "🚀 Enviando a n8n...")

        res = crear_workflow(estado.get(uid))

        if "ok" in res:
            await context.bot.send_message(chat_id, "✅ Workflow creado correctamente")
        else:
            await context.bot.send_message(chat_id, f"❌ Error:\n{res['error']}")

    elif query.data == "mejorar":
        await context.bot.send_message(chat_id, "🧠 Mejorando workflow con IA...")

        mejorado = llamar_ia(agente_optimizador(estado.get(uid)))

        wf = agente_validador(mejorado)

        if wf:
            estado[uid] = wf
            await context.bot.send_message(chat_id, "✅ Mejorado correctamente")
        else:
            await context.bot.send_message(chat_id, "❌ No se pudo mejorar")

    elif query.data == "regen":
        await context.bot.send_message(chat_id, "🔄 Regenerando flujo...")
        await procesar(query, context, "regenerar flujo completo")

# =============================
# 📩 MENSAJES
# =============================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)

# =============================
# 🚀 INICIO
# =============================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW ULTRA SaaS ACTIVO")
app.run_polling()
