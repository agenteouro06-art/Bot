import os
import json
import asyncio
import requests
import re
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# 🔥 ENV
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER"))
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY") # Necesario para la IA de Anthropic

estado = {}

# =========================
# 🧠 DETECTOR INTELIGENTE (FALLBACK)
# =========================
def detectar_tipo(texto):
    t = texto.lower()
    if "whatsapp" in t and ("captura" in t or "imagen" in t):
        return "validador_pago"
    if "pedido" in t or "restaurante" in t:
        return "pedidos_restaurante"
    return "basico"


# =========================
# 🏗 GENERADORES MOCK (RESPALDO)
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
# 🤖 MOTOR MULTI-AGENTE (CLAUDE 3 HAIKU)
# =========================
def peticion_claude(texto_usuario):
    """
    Envía el prompt a Claude 3 Haiku para generar la estructura JSON del workflow.
    """
    if not CLAUDE_API_KEY:
        print("⚠️ No se encontró CLAUDE_API_KEY en el entorno.")
        return None

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    # El System Prompt define el comportamiento del Agente de Diseño
    prompt_sistema = """Eres CLAW, un sistema multi-agente experto en arquitectura de n8n.
Tu objetivo es traducir los requerimientos del usuario en un JSON válido de workflow para n8n.
Debes crear la estructura completa con 'nodes' y 'connections'.
Analiza el requerimiento: si piden Google Sheets, usa 'n8n-nodes-base.googleSheets'. Si piden IA, añade llamadas HTTP o nodos correspondientes.
REGLA ESTRICTA: Devuelve ÚNICAMENTE un objeto JSON válido. Nada de saludos, nada de explicaciones en markdown, solo el JSON puro."""

    payload = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 4000,
        "system": prompt_sistema,
        "messages": [
            {"role": "user", "content": f"Por favor, crea un flujo en n8n para el siguiente requerimiento: {texto_usuario}"}
        ]
    }

    try:
        r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        r.raise_for_status()
        respuesta = r.json()['content'][0]['text']
        
        # Expresión regular para extraer solo el JSON ignorando el posible relleno del modelo
        match = re.search(r'\{.*\}', respuesta, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(respuesta)
    except Exception as e:
        print(f"🔥 Error en el Agente de Claude: {e}")
        return None

# =========================
# ASYNC WRAPPER PARA CLAUDE
# =========================
async def generar_flujo_ia(texto_usuario):
    """
    Ejecuta la llamada HTTP a Claude en un hilo separado para no bloquear el bot
    """
    return await asyncio.to_thread(peticion_claude, texto_usuario)


# =========================
# 🔧 NORMALIZAR
# =========================
def normalizar(wf):
    wf.pop("id", None)
    wf.pop("active", None)

    for n in wf.get("nodes", []):
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
# 🧠 ORQUESTADOR PRINCIPAL
# =========================
async def procesar(update, context, texto):

    uid = update.effective_user.id
    mensaje_estado = await update.message.reply_text("🧠 Agentes analizando y diseñando flujo...")

    # 1. Intentamos que la IA diseñe el JSON dinámico
    wf = await generar_flujo_ia(texto)

    # 2. Fallback si la IA falla o la API Key no está configurada
    if wf:
        await mensaje_estado.edit_text("🏗 Diseño generado exitosamente por Agente Claude Haiku.")
    else:
        tipo = detectar_tipo(texto)
        await mensaje_estado.edit_text(f"⚠️ IA no disponible. Usando template predefinido: {tipo}")
        
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
        "💀 CLAW GOD FLOW listo para desplegar",
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
        # Intentamos obtener el ID del workflow creado o mostramos todo el dict
        id_creado = res.get('id', 'Error') if isinstance(res, dict) else 'Respuesta inesperada'
        await query.message.reply_text(f"✅ Workflow creado exitosamente. ID: {id_creado}")

    elif query.data == "ver":
        txt = json.dumps(estado[uid], indent=2)
        # Telegram permite max ~4096 caracteres. Mostramos los primeros 4000.
        await query.message.reply_text(f"
