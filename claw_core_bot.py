import os
import json
import asyncio
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# 🔥 ENV
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

estado = {}

# =========================
# 🧠 DETECTOR INTELIGENTE
# =========================
def detectar_tipo(texto):
    t = texto.lower()

    if "whatsapp" in t and ("captura" in t or "imagen" in t):
        return "validador_pago"

    if "pedido" in t or "restaurante" in t:
        return "pedidos_restaurante"

    return "basico"


# =========================
# 🏗 GENERADORES REALES
# =========================

def flujo_validador():
    return {
        "name": "CLAW - Validador WhatsApp",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook WhatsApp",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "whatsapp-in",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },
            {
                "id": "2",
                "name": "Set Datos",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [400, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "imagen_url", "value": "={{$json.body.image}}"}
                        ]
                    }
                }
            },
            {
                "id": "3",
                "name": "HTTP Imagen",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 2,
                "position": [600, 300],
                "parameters": {
                    "url": "={{$json.imagen_url}}",
                    "responseFormat": "file"
                }
            },
            {
                "id": "4",
                "name": "OCR Mock",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [800, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "texto", "value": "REF123 MONTO 50000"}
                        ]
                    }
                }
            },
            {
                "id": "5",
                "name": "Banco Mock",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [1000, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "ref_banco", "value": "REF123"},
                            {"name": "monto_banco", "value": "50000"}
                        ]
                    }
                }
            },
            {
                "id": "6",
                "name": "Comparar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [1200, 300],
                "parameters": {
                    "functionCode": """
const ok = $json.texto.includes($json.ref_banco) && $json.texto.includes($json.monto_banco);
return [{ json: { aprobado: ok } }];
"""
                }
            }
        ],
        "connections": {
            "Webhook WhatsApp": {"main": [[{"node": "Set Datos", "type": "main"}]]},
            "Set Datos": {"main": [[{"node": "HTTP Imagen", "type": "main"}]]},
            "HTTP Imagen": {"main": [[{"node": "OCR Mock", "type": "main"}]]},
            "OCR Mock": {"main": [[{"node": "Banco Mock", "type": "main"}]]},
            "Banco Mock": {"main": [[{"node": "Comparar", "type": "main"}]]}
        },
        "settings": {}
    }


def flujo_pedidos():
    return {
        "name": "CLAW - Pedidos Restaurante",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook Pedido",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "pedido",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },
            {
                "id": "2",
                "name": "Google Sheets",
                "type": "n8n-nodes-base.googleSheets",
                "typeVersion": 4,
                "position": [400, 300],
                "parameters": {
                    "operation": "read"
                }
            },
            {
                "id": "3",
                "name": "Formatear Menu",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [600, 300],
                "parameters": {
                    "functionCode": """
let menu = items.map(i => i.json.nombre + " - $" + i.json.precio).join("\\n");
return [{json: {menu}}];
"""
                }
            }
        ],
        "connections": {
            "Webhook Pedido": {"main": [[{"node": "Google Sheets"}]]},
            "Google Sheets": {"main": [[{"node": "Formatear Menu"}]]}
        },
        "settings": {}
    }


def flujo_basico():
    return {
        "name": "CLAW Básico",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "parameters": {
                    "path": "test",
                    "httpMethod": "POST"
                }
            }
        ],
        "connections": {},
        "settings": {}
    }


# =========================
# 🔧 NORMALIZAR
# =========================
def normalizar(wf):
    wf.pop("id", None)
    wf.pop("active", None)

    for n in wf["nodes"]:
        n["parameters"] = n.get("parameters", {})
        n["typeVersion"] = n.get("typeVersion", 1)

    return wf


# =========================
# 🚀 CREAR EN N8N
# =========================
def crear_workflow(wf):
    wf = normalizar(wf)

    r = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        headers={
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json"
        },
        json=wf
    )

    return r.json()


# =========================
# 🧠 MULTI-AGENTE REAL
# =========================
async def procesar(update, context, texto):

    uid = update.effective_user.id

    await update.message.reply_text("🧠 Analizando intención...")
    tipo = detectar_tipo(texto)

    await update.message.reply_text(f"🏗 Tipo detectado: {tipo}")

    if tipo == "validador_pago":
        wf = flujo_validador()
    elif tipo == "pedidos_restaurante":
        wf = flujo_pedidos()
    else:
        wf = flujo_basico()

    estado[uid] = wf

    kb = [
        [
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="crear"),
            InlineKeyboardButton("📄 Ver JSON", callback_data="ver")
        ],
        [
            InlineKeyboardButton("🔄 Regenerar", callback_data="regen")
        ]
    ]

    await update.message.reply_text(
        "💀 CLAW GOD FLOW generado correctamente",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# =========================
# 🎛 BOTONES
# =========================
async def botones(update, context):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    if query.data == "crear":
        res = crear_workflow(estado[uid])
        await query.message.reply_text(f"✅ {res}")

    elif query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        await query.message.reply_text(f"```json\n{txt[:4000]}\n```", parse_mode="Markdown")

    elif query.data == "regen":
        await query.message.reply_text("🔄 Regenerando inteligente...")
        await procesar(query, context, "regen avanzado")


# =========================
# 📩 MENSAJES
# =========================
async def handle(update, context):
    if update.effective_user.id != ALLOWED_USER:
        return

    await procesar(update, context, update.message.text)


# =========================
# 🚀 INICIO
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print("🔥 CLAW GOD REAL ACTIVO")
app.run_polling()
