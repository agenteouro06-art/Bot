import os
import json
import uuid
import requests
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# =========================
# 🔥 ENV
# =========================
load_dotenv("/home/mau/claw_core/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

print("🔥 BOT ACTIVO (GIFHUD READY)")

# =========================
# 🧠 IA (OPENROUTER)
# =========================
def llamar_ia(system, user_msg):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-3-haiku",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg}
                ]
            },
            timeout=30
        )

        data = r.json()

        if "error" in data:
            print("❌ ERROR IA:", data)
            return None

        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print("❌ ERROR IA:", e)
        return None

# =========================
# 🧠 PROMPT N8N (CONTROL TOTAL)
# =========================
SYS_N8N = """
Eres experto en n8n.

REGLAS CRÍTICAS:

- SOLO puedes usar estos nodos:
  - n8n-nodes-base.webhook
  - n8n-nodes-base.httpRequest
  - n8n-nodes-base.set
  - n8n-nodes-base.if
  - n8n-nodes-base.function
  - n8n-nodes-base.respondToWebhook
  - n8n-nodes-base.gmail
  - n8n-nodes-base.telegram

- PROHIBIDO inventar nodos
- PROHIBIDO usar nodos que no existan

- Devuelve SOLO JSON válido
- SIN markdown
- SIN explicación
- Flujo COMPLETO y FUNCIONAL
"""

# =========================
# 🔥 LIMPIAR JSON IA
# =========================
def limpiar_json_ia(raw):
    if not raw:
        return None
    try:
        if "```" in raw:
            raw = raw.split("```")[1]
            raw = raw.replace("json", "").strip()

        start = raw.find("{")
        end = raw.rfind("}") + 1

        if start == -1 or end == -1:
            return None

        raw = raw[start:end]

        return json.loads(raw)

    except Exception as e:
        print("❌ JSON ERROR:", e)
        return None

# =========================
# 🔥 FALLBACK SEGURO
# =========================
def fallback():
    return {
        "name": "Fallback Workflow",
        "nodes": [
            {
                "id": str(uuid.uuid4()),
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [200, 300],
                "parameters": {
                    "path": "test",
                    "httpMethod": "POST"
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Procesar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [450, 300],
                "parameters": {
                    "functionCode": "return [{json:{ok:true}}];"
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Responder",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [700, 300],
                "parameters": {
                    "responseData": "ok"
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Procesar", "type": "main", "index": 0}]]
            },
            "Procesar": {
                "main": [[{"node": "Responder", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }

# =========================
# 🧠 GENERADOR
# =========================
def generar_flujo(prompt):
    print("🚀 Generando flujo...")

    raw = llamar_ia(SYS_N8N, prompt)

    print("📥 RAW:", raw)

    wf = limpiar_json_ia(raw)

    if not wf or not wf.get("nodes"):
        print("⚠️ Usando fallback")
        return fallback()

    return wf

# =========================
# 🔥 LIMPIAR PARA N8N
# =========================
def limpiar_para_n8n(wf):
    wf.pop("id", None)
    wf.pop("active", None)
    wf.pop("meta", None)
    wf.pop("versionId", None)
    wf.pop("createdAt", None)
    wf.pop("updatedAt", None)

    for n in wf["nodes"]:
        n.pop("credentials", None)

    wf["settings"] = {}

    return wf

# =========================
# 🔗 CREAR EN N8N
# =========================
def crear_n8n(wf):
    wf = limpiar_para_n8n(wf)

    r = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        headers={
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json"
        },
        json=wf
    )

    print("STATUS:", r.status_code)
    print("RESP:", r.text[:500])

    try:
        return r.json()
    except:
        return {}

# =========================
# 🤖 TELEGRAM BOT
# =========================
async def handle(update, context):
    texto = update.message.text

    await update.message.reply_text("🧠 MODO AUTÓNOMO TOTAL")

    wf = generar_flujo(texto)

    res = crear_n8n(wf)

    if res.get("id"):
        await update.message.reply_text(f"✅ Flujo creado: {res['id']}")
    else:
        await update.message.reply_text(f"❌ Error:\n{res}")

# =========================
# 🚀 START
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT, handle))

app.run_polling()
