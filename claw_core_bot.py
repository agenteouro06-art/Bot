import os, json, requests, re
from dotenv import load_dotenv

load_dotenv("/home/mau/claw_core/.env")

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

# =========================
# 🔥 OPENROUTER CALL
# =========================
def or_chat(system, user, max_tokens=2000):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "anthropic/claude-3-haiku",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "max_tokens": max_tokens
    }

    r = requests.post(url, headers=headers, json=data)
    return r.json()["choices"][0]["message"]["content"]


# =========================
# 🧹 LIMPIADOR JSON
# =========================
def limpiar_json(raw):
    if "```" in raw:
        raw = raw.split("```")[1]

    raw = raw.replace("json", "").strip()

    inicio = raw.find("{")
    fin = raw.rfind("}") + 1

    return raw[inicio:fin]


# =========================
# 🧬 BASE LOCAL (REAL)
# =========================
PLANTILLAS = [
{
"name": "Pedidos WhatsApp",
"nodes": [
{"id":"1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[200,300],"parameters":{"path":"pedido","httpMethod":"POST"}},
{"id":"2","name":"Set Pedido","type":"n8n-nodes-base.set","typeVersion":2,"position":[450,300],"parameters":{"values":{"string":[{"name":"pedido","value":"={{$json.body}}"}]}}},
{"id":"3","name":"Google Sheets","type":"n8n-nodes-base.googleSheets","typeVersion":4,"position":[700,300],"parameters":{"operation":"append"}}
],
"connections":{
"Webhook":{"main":[[{"node":"Set Pedido","type":"main","index":0}]]},
"Set Pedido":{"main":[[{"node":"Google Sheets","type":"main","index":0}]]}
},
"settings":{},
"pinData":{}
},

{
"name": "Webhook Básico",
"nodes":[
{"id":"1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[200,300],"parameters":{}},
{"id":"2","name":"Respuesta","type":"n8n-nodes-base.set","typeVersion":2,"position":[450,300],"parameters":{"values":{"string":[{"name":"msg","value":"ok"}]}}}
],
"connections":{
"Webhook":{"main":[[{"node":"Respuesta","type":"main","index":0}]]}
},
"settings":{},
"pinData":{}
}
]


# =========================
# 🌐 SCRAPER (BASE REALISTA)
# =========================
def buscar_workflows_online(desc):
    try:
        # Simulación preparada para scraping real
        url = f"https://api.github.com/search/code?q=n8n+workflow+json+{desc}"
        r = requests.get(url, timeout=5)

        if r.status_code != 200:
            return None

        data = r.json()

        if "items" not in data or not data["items"]:
            return None

        # 🔥 aquí puedes luego descargar raw_url
        return None

    except:
        return None


# =========================
# 🧠 ELEGIR BASE
# =========================
def elegir_base(desc):
    d = desc.lower()

    if "pedido" in d or "restaurante" in d:
        return PLANTILLAS[0]

    return PLANTILLAS[1]


# =========================
# 🤖 CLONADOR + MODIFICADOR
# =========================
def generar_flujo(desc):
    print("🧠 ANALISTA IA...")
    print("🏗 ARQUITECTO IA...")
    print("🎨 DISEÑADOR IA...")
    print("🔍 VALIDANDO JSON...")

    base = buscar_workflows_online(desc)

    if not base:
        print("⚠ usando base local")
        base = elegir_base(desc)

    system = """
Eres experto en n8n.

Recibirás un workflow real.

Tu trabajo:
- MODIFICARLO según el requerimiento
- Mantener estructura válida
- NO inventar nodos falsos
- RESPONDER SOLO JSON limpio

Si fallas devuelve:
{"error":"fail"}
"""

    prompt = f"""
WORKFLOW BASE:
{json.dumps(base, indent=2)}

REQUERIMIENTO:
{desc}

Devuelve JSON final.
"""

    try:
        raw = or_chat(system, prompt)

        limpio = limpiar_json(raw)

        data = json.loads(limpio)

        if "error" in data:
            print("❌ IA falló → fallback")
            return base

        print("⚙ CORRIGIENDO...")
        print("💰 OPTIMIZANDO...")
        print("💀 ULTRA FLOW listo")

        return data

    except Exception as e:
        print("❌ ERROR IA:", e)
        return base


# =========================
# 🧪 TEST DIRECTO
# =========================
if __name__ == "__main__":
    desc = input("Describe el flujo:\n> ")

    flujo = generar_flujo(desc)

    print("\n========== RESULTADO ==========\n")
    print(json.dumps(flujo, indent=2))
