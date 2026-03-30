import requests
import json
import time

N8N_URL = "http://192.168.101.31:5678/api/v1/workflows"
N8N_API_KEY = "TU_API_KEY_AQUI"

HEADERS = {
    "X-N8N-API-KEY": N8N_API_KEY,
    "Content-Type": "application/json"
}

# =========================
# 🧠 GENERADOR REAL (NO INVENTA)
# =========================
def generar_workflow_real():
    return {
        "name": "CLAW WhatsApp OCR Validator",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [200, 300],
                "parameters": {
                    "path": "claw-whatsapp",
                    "httpMethod": "POST",
                    "responseMode": "onReceived"
                }
            },
            {
                "id": "2",
                "name": "HTTP OCR",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 1,
                "position": [500, 300],
                "parameters": {
                    "url": "https://api.ocr.space/parse/image",
                    "method": "POST",
                    "sendBinaryData": True
                }
            },
            {
                "id": "3",
                "name": "Email Read",
                "type": "n8n-nodes-base.emailReadImap",
                "typeVersion": 1,
                "position": [800, 300],
                "parameters": {
                    "mailbox": "INBOX"
                }
            },
            {
                "id": "4",
                "name": "Comparar Datos",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [1100, 300],
                "parameters": {
                    "functionCode": """
const texto = $json["ParsedResults"]?.[0]?.ParsedText || "";
const correo = $node["Email Read"].json?.text || "";

let match = false;

if (texto && correo) {
    match = texto.includes(correo.substring(0, 10));
}

return [{ json: { match } }];
"""
                }
            },
            {
                "id": "5",
                "name": "IF Coincide",
                "type": "n8n-nodes-base.if",
                "typeVersion": 1,
                "position": [1300, 300],
                "parameters": {
                    "conditions": {
                        "boolean": [
                            {
                                "value1": "={{$json['match']}}",
                                "operation": "isTrue"
                            }
                        ]
                    }
                }
            },
            {
                "id": "6",
                "name": "Responder WhatsApp",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 1,
                "position": [1500, 200],
                "parameters": {
                    "url": "https://api.whatsapp.com/send",
                    "method": "POST"
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "HTTP OCR", "type": "main", "index": 0}]]
            },
            "HTTP OCR": {
                "main": [[{"node": "Email Read", "type": "main", "index": 0}]]
            },
            "Email Read": {
                "main": [[{"node": "Comparar Datos", "type": "main", "index": 0}]]
            },
            "Comparar Datos": {
                "main": [[{"node": "IF Coincide", "type": "main", "index": 0}]]
            },
            "IF Coincide": {
                "main": [
                    [{"node": "Responder WhatsApp", "type": "main", "index": 0}],
                    []
                ]
            }
        },
        "settings": {}
    }

# =========================
# 🔍 VALIDADOR JSON (MODO DIOS)
# =========================
def validar_json(workflow):
    try:
        json.dumps(workflow)
        if "name" not in workflow:
            raise Exception("Falta 'name'")
        if "settings" not in workflow:
            workflow["settings"] = {}
        return True
    except Exception as e:
        print("❌ JSON inválido:", e)
        return False

# =========================
# 🚀 CREAR WORKFLOW (CON REINTENTO)
# =========================
def crear_workflow():
    workflow = generar_workflow_real()

    if not validar_json(workflow):
        print("⚠ Corrigiendo JSON...")
        workflow["settings"] = {}

    for intento in range(3):
        try:
            response = requests.post(
                N8N_URL,
                headers=HEADERS,
                data=json.dumps(workflow)
            )

            if response.status_code in [200, 201]:
                print("✅ WORKFLOW CREADO:")
                print(response.json())
                return

            else:
                print("⚠ Error:", response.text)

        except Exception as e:
            print("❌ Error conexión:", e)

        time.sleep(2)

    print("🔥 FALLÓ DESPUÉS DE 3 INTENTOS")

# =========================
# 🤖 BOTONES TELEGRAM FIX
# =========================
def botones():
    return {
        "inline_keyboard": [
            [
                {"text": "🚀 Crear en n8n", "callback_data": "crear"},
                {"text": "📄 Ver JSON", "callback_data": "ver_json"}
            ],
            [
                {"text": "🔄 Regenerar", "callback_data": "regen"}
            ]
        ]
    }

# =========================
# 🧠 MODO DIOS
# =========================
def modo_dios():
    print("🔥 CLAW MODO DIOS ACTIVADO")
    crear_workflow()

# =========================
# ▶ EJECUCIÓN
# =========================
if __name__ == "__main__":
    modo_dios()
