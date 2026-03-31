import os, json, requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# 🔥 CARGAR ENV (CORREGIDO)
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER   = int(os.getenv("ALLOWED_USER", "0"))
N8N_URL        = os.getenv("N8N_URL")
N8N_API_KEY    = os.getenv("N8N_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

estado = {}

# 🧠 PLANTILLA BASE REAL (FUNCIONAL)
def flujo_base():
    return {
        "name": "CLAW Flow Base",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "claw",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },
            {
                "id": "2",
                "name": "Set",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [450, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "msg", "value": "ok"}
                        ]
                    }
                }
            },
            {
                "id": "3",
                "name": "Responder",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [700, 300],
                "parameters": {}
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Set", "type": "main", "index": 0}]]
            },
            "Set": {
                "main": [[{"node": "Responder", "type": "main", "index": 0}]]
            }
        },
        "settings": {},
        "pinData": {}
    }

# 🔥 CORRECCIÓN AUTOMÁTICA (CLAVE)
def arreglar_workflow(wf):
    if not isinstance(wf, dict):
        return flujo_base()

    wf["name"] = wf.get("name", "CLAW AUTO FLOW")
    wf["settings"] = wf.get("settings", {})
    wf["pinData"] = wf.get("pinData", {})
    wf["connections"] = wf.get("connections", {})

    for i, node in enumerate(wf.get("nodes", [])):
        node["id"] = str(i + 1)
        node["name"] = node.get("name", f"Nodo {i+1}")
        node["typeVersion"] = node.get("typeVersion", 1)
        node["position"] = node.get("position", [200 + i*250, 300])
        node["parameters"] = node.get("parameters", {})

    return wf

# 🤖 GENERADOR SIMPLE (SIN INVENTAR COSAS ROTAS)
def generar_flujo(desc):
    t = desc.lower()

    # 🔥 CASO: TRANSFERENCIAS
    if "transferencia" in t or "banco" in t:
        return {
            "name": "Validar Transferencia",
            "nodes": [
                {
                    "id": "1",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2,
                    "position": [200, 300],
                    "parameters": {
                        "path": "validar",
                        "httpMethod": "POST",
                        "responseMode": "lastNode"
                    }
                },
                {
                    "id": "2",
                    "name": "Set Datos",
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 2,
                    "position": [450, 300],
                    "parameters": {
                        "values": {
                            "string": [
                                {"name": "status", "value": "procesando"}
                            ]
                        }
                    }
                },
                {
                    "id": "3",
                    "name": "IF Validar",
                    "type": "n8n-nodes-base.if",
                    "typeVersion": 1,
                    "position": [700, 300],
                    "parameters": {
                        "conditions": {
                            "string": [
                                {
                                    "value1": "={{$json.status}}",
                                    "operation": "contains",
                                    "value2": "ok"
                                }
                            ]
                        }
                    }
                },
                {
                    "id": "4",
                    "name": "Responder",
                    "type": "n8n-nodes-base.respondToWebhook",
                    "typeVersion": 1,
                    "position": [950, 300],
                    "parameters": {}
                }
            ],
            "connections": {
                "Webhook": {
                    "main": [[{"node": "Set Datos", "type": "main", "index": 0}]]
                },
                "Set Datos": {
                    "main": [[{"node": "IF Validar", "type": "main", "index": 0}]]
                },
                "IF Validar": {
                    "main": [[{"node": "Responder", "type": "main", "index": 0}]]
                }
            },
            "settings": {},
            "pinData": {}
        }

    # 🔥 DEFAULT
    return flujo_base()

# 🚀 CREAR EN N8N
def crear_n8n(wf):
    try:
        r = requests.post(
            f"{N8N_URL}/api/v1/workflows",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            },
            json=wf,
            timeout=20
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# 🚀 MENSAJES
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ALLOWED_USER:
        return

    texto = update.message.text

    await update.message.reply_text("🧠 Procesando...")

    wf = generar_flujo(texto)
    wf = arreglar_workflow(wf)

    estado[uid] = wf

    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="ver")
        ]
    ]

    await update.message.reply_text(
        f"✅ Flujo generado:\n{wf['name']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# 🎛 BOTONES
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    chat_id = query.message.chat.id

    if query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await context.bot.send_message(chat_id, f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "crear":
        await context.bot.send_message(chat_id, "🚀 Creando en n8n...")

        wf = arreglar_workflow(estado[uid])
        res = crear_n8n(wf)

        await context.bot.send_message(chat_id, f"✅ Respuesta:\n{res}")

# 🚀 INICIO
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 BOT FUNCIONAL INICIADO")
app.run_polling()
