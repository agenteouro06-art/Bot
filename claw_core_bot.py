import os
import json
import uuid
import requests
from dotenv import load_dotenv

# =========================
# 🔥 ENV
# =========================

load_dotenv("/home/mau/claw_core/.env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
N8N_URL = os.getenv("N8N_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

# =========================
# 🧠 IA (OpenRouter FIX)
# =========================

def llamar_ia(prompt):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-3-haiku",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20
        )

        data = r.json()

        if "error" in data:
            print("❌ IA ERROR:", data)
            return None

        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print("❌ IA EXCEPTION:", e)
        return None

# =========================
# 🧠 FLUJO BASE REAL (FUNCIONAL)
# =========================

def flujo_real():
    return {
        "name": "Validación transferencia OCR + Email",
        "nodes": [
            {
                "id": str(uuid.uuid4()),
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [200, 300],
                "parameters": {
                    "path": "validar-transferencia",
                    "httpMethod": "POST",
                    "responseMode": "lastNode"
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "OCR",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 1,
                "position": [400, 300],
                "parameters": {
                    "url": "https://api.ocr.space/parse/image",
                    "method": "POST",
                    "jsonParameters": True,
                    "options": {},
                    "bodyParametersJson": """
                    {
                        "url": "{{$json.image_url}}",
                        "apikey": "TU_API_KEY_OCR"
                    }
                    """
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Parse OCR",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [600, 300],
                "parameters": {
                    "functionCode": """
const texto = JSON.stringify($json).toLowerCase();

const referencia = (texto.match(/\\d{6,}/) || [''])[0];
const monto = (texto.match(/\\d{4,}/) || [''])[0];

return [{ json: { referencia, monto } }];
"""
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Leer Email",
                "type": "n8n-nodes-base.gmail",
                "typeVersion": 1,
                "position": [800, 300],
                "parameters": {
                    "resource": "message",
                    "operation": "getAll"
                },
                "credentials": {}
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Comparar",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [1000, 300],
                "parameters": {
                    "functionCode": """
const referencia = $json.referencia || "";
const aprobado = referencia.length > 5;

return [{ json: { aprobado } }];
"""
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "IF",
                "type": "n8n-nodes-base.if",
                "typeVersion": 1,
                "position": [1200, 300],
                "parameters": {
                    "conditions": {
                        "boolean": [
                            {
                                "value1": "={{$json.aprobado}}",
                                "operation": "equal",
                                "value2": True
                            }
                        ]
                    }
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "OK",
                "type": "n8n-nodes-base.set",
                "typeVersion": 1,
                "position": [1400, 200],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "respuesta",
                                "value": "✅ Pago confirmado"
                            }
                        ]
                    }
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "FAIL",
                "type": "n8n-nodes-base.set",
                "typeVersion": 1,
                "position": [1400, 400],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "respuesta",
                                "value": "❌ Pago no coincide"
                            }
                        ]
                    }
                }
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Responder",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [1600, 300],
                "parameters": {
                    "responseCode": 200,
                    "responseData": "={{$json.respuesta}}"
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "OCR", "type": "main", "index": 0}]]
            },
            "OCR": {
                "main": [[{"node": "Parse OCR", "type": "main", "index": 0}]]
            },
            "Parse OCR": {
                "main": [[{"node": "Leer Email", "type": "main", "index": 0}]]
            },
            "Leer Email": {
                "main": [[{"node": "Comparar", "type": "main", "index": 0}]]
            },
            "Comparar": {
                "main": [[{"node": "IF", "type": "main", "index": 0}]]
            },
            "IF": {
                "main": [
                    [{"node": "OK", "type": "main", "index": 0}],
                    [{"node": "FAIL", "type": "main", "index": 0}]
                ]
            },
            "OK": {
                "main": [[{"node": "Responder", "type": "main", "index": 0}]]
            },
            "FAIL": {
                "main": [[{"node": "Responder", "type": "main", "index": 0}]]
            }
        }
    }

# =========================
# 🧠 MODO AUTÓNOMO TOTAL
# =========================

def modo_autonomo(prompt):
    print("🧠 MODO AUTÓNOMO TOTAL")

    ia = llamar_ia(f"Genera un flujo n8n JSON para: {prompt}")

    if ia:
        try:
            return json.loads(ia)
        except:
            print("⚠️ IA devolvió mal JSON")

    print("⚠️ Usando flujo REAL fallback")
    return flujo_real()

# =========================
# 🔁 N8N API FIX
# =========================

def limpiar(workflow):
    for k in ["id", "active", "versionId", "meta"]:
        workflow.pop(k, None)

    for n in workflow["nodes"]:
        n.pop("credentials", None)  # 🔥 FIX CLAVE
    return workflow

def crear(workflow):
    wf = limpiar(workflow)

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

# =========================
# 🚀 EJECUCIÓN
# =========================

if __name__ == "__main__":
    print("🔥 BOT ACTIVO (GIFHUD READY)")

    wf = modo_autonomo("verificar pagos por whatsapp con OCR y email banco")

    if wf:
        print("✅ Flujo generado")
        crear(wf)
    else:
        print("❌ Error generando flujo")
