“””
╔══════════════════════════════════════════════════════════╗
║           CLAW CORE BOT — Asistente n8n con IA          ║
║  Telegram + Claude Haiku + n8n API + Ejecución Ubuntu   ║
╚══════════════════════════════════════════════════════════╝
“””

import os
import json
import asyncio
import subprocess
import requests
import anthropic
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
ApplicationBuilder, MessageHandler, CommandHandler,
ContextTypes, CallbackQueryHandler, filters
)

# ─────────────────────────────────────────────

# ENV

# ─────────────────────────────────────────────

load_dotenv(”/home/mau/claw_core/.env”)

TELEGRAM_TOKEN  = os.getenv(“TELEGRAM_TOKEN”)
ALLOWED_USER    = int(os.getenv(“ALLOWED_USER”))
N8N_URL         = os.getenv(“N8N_URL”)          # ej: http://localhost:5678
N8N_API_KEY     = os.getenv(“N8N_API_KEY”)
ANTHROPIC_KEY   = os.getenv(“ANTHROPIC_API_KEY”)

claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# ─────────────────────────────────────────────

# ESTADO POR USUARIO

# ─────────────────────────────────────────────

estado = {}   # uid → { “flujo”: {…}, “cmd”: “…”, “historial”: […] }

def get_estado(uid):
if uid not in estado:
estado[uid] = {“flujo”: None, “cmd”: None, “historial”: []}
return estado[uid]

# ══════════════════════════════════════════════

# BLOQUE 1 — CLASIFICADOR DE INTENCIÓN (IA)

# ══════════════════════════════════════════════

SYSTEM_CLASIFICADOR = “””
Eres el clasificador de intenciones de CLAW CORE, un asistente para desarrolladores n8n.
Analiza el mensaje del usuario y responde SOLO con un JSON válido, sin markdown, sin explicaciones.

Formato de respuesta:
{
“tipo”: “<TIPO>”,
“resumen”: “<resumen breve de lo que pide>”,
“datos”: {}
}

Tipos posibles:

- “FLUJO_CREAR”   → pide crear un flujo/workflow nuevo en n8n
- “FLUJO_REPARAR” → pide arreglar, depurar o modificar un flujo existente
- “FLUJO_LISTAR”  → pide ver los flujos que tiene en n8n
- “FLUJO_VER”     → pide ver el JSON o detalle de un flujo específico
- “FLUJO_ACTIVAR” → pide activar o desactivar un flujo
- “CMD_SISTEMA”   → quiere ejecutar un comando en el servidor Ubuntu (memoria, disco, instalar, etc.)
- “PREGUNTA”      → pregunta general sobre n8n, automatizaciones, su negocio
- “OTRO”          → todo lo demás

Para CMD_SISTEMA incluye en “datos”: { “cmd_sugerido”: “<comando bash exacto>” }
Para FLUJO_CREAR incluye en “datos”: { “nombre”: “<nombre sugerido>”, “descripcion”: “<qué hace el flujo>” }
Para FLUJO_REPARAR incluye en “datos”: { “workflow_id”: null }
“””

async def clasificar_intencion(texto: str) -> dict:
“”“Usa Claude Haiku para clasificar qué quiere el usuario.”””
try:
r = claude.messages.create(
model=“claude-haiku-4-5”,
max_tokens=400,
system=SYSTEM_CLASIFICADOR,
messages=[{“role”: “user”, “content”: texto}]
)
raw = r.content[0].text.strip()
return json.loads(raw)
except Exception as e:
return {“tipo”: “OTRO”, “resumen”: texto, “datos”: {}, “error”: str(e)}

# ══════════════════════════════════════════════

# BLOQUE 2 — GENERADOR DE FLUJOS n8n (IA)

# ══════════════════════════════════════════════

SYSTEM_N8N_EXPERTO = “””
Eres un experto en n8n que genera workflows JSON válidos y funcionales.
El usuario necesita flujos para vender a negocios (restaurantes, tiendas, etc.).

REGLAS CRÍTICAS:

1. Devuelve SOLO el JSON del workflow, sin markdown, sin texto extra.
1. El JSON debe ser importable directamente en n8n.
1. Usa SIEMPRE estos campos en el root: name, nodes, connections, settings, pinData.
1. Cada nodo DEBE tener: id (string único), name, type, typeVersion, position ([x,y]), parameters.
1. Las conexiones van en “connections” con la estructura exacta de n8n.
1. Usa nodos reales de n8n: n8n-nodes-base.webhook, n8n-nodes-base.httpRequest,
   n8n-nodes-base.googleSheets, n8n-nodes-base.sendEmail, n8n-nodes-base.set,
   n8n-nodes-base.if, n8n-nodes-base.whatsappBusiness, @n8n/n8n-nodes-langchain.openAi, etc.
1. Para flujos de restaurante/pedidos usa Webhook de entrada + validación + respuesta.
1. Los flujos deben ser COMPLETOS y FUNCIONALES, no esqueletos.
1. Espaciado de posiciones: incrementa X en 250 por cada nodo, Y base en 300.

Estructura de conexión ejemplo:
“connections”: {
“NombreNodo1”: {
“main”: [[{“node”: “NombreNodo2”, “type”: “main”, “index”: 0}]]
}
}
“””

async def generar_flujo_ia(descripcion: str, flujo_base: dict = None) -> dict:
“”“Genera o repara un flujo n8n usando Claude.”””

```
if flujo_base:
    prompt = f"""Repara y mejora este flujo n8n que tiene problemas.
```

Flujo actual (con errores):
{json.dumps(flujo_base, indent=2)}

Problemas reportados / cambios necesarios:
{descripcion}

Devuelve el flujo COMPLETO corregido en JSON válido.”””
else:
prompt = f””“Crea un workflow n8n completo y funcional para:
{descripcion}

El flujo debe ser profesional, listo para vender a negocios.
Devuelve SOLO el JSON del workflow.”””

```
r = claude.messages.create(
    model="claude-haiku-4-5",
    max_tokens=4000,
    system=SYSTEM_N8N_EXPERTO,
    messages=[{"role": "user", "content": prompt}]
)

raw = r.content[0].text.strip()

# Limpiar posibles bloques markdown
if raw.startswith("```"):
    raw = raw.split("```")[1]
    if raw.startswith("json"):
        raw = raw[4:]
raw = raw.strip()

return json.loads(raw)
```

# ══════════════════════════════════════════════

# BLOQUE 3 — RESPUESTAS GENERALES (IA)

# ══════════════════════════════════════════════

SYSTEM_ASISTENTE = “””
Eres CLAW CORE, el asistente personal de Mau, experto en n8n y automatizaciones.
Mau tiene un negocio vendiendo flujos de n8n a restaurantes y otros negocios.

Tu personalidad: directo, técnico, eficiente. Ayudas a crear flujos rentables.
Respondes en español. Máximo 3-4 párrafos en respuestas normales.

Cuando el usuario pregunte sobre estrategias de negocio, precios, qué flujos vender,
dales consejos prácticos y concretos basados en el mercado de automatizaciones.
“””

async def respuesta_general(texto: str, historial: list) -> str:
“”“Responde preguntas generales con contexto del historial.”””
msgs = historial[-10:] + [{“role”: “user”, “content”: texto}]

```
r = claude.messages.create(
    model="claude-haiku-4-5",
    max_tokens=1000,
    system=SYSTEM_ASISTENTE,
    messages=msgs
)
return r.content[0].text.strip()
```

# ══════════════════════════════════════════════

# BLOQUE 4 — COMANDOS DE SISTEMA

# ══════════════════════════════════════════════

async def explicar_comando(cmd: str) -> str:
“”“Usa IA para explicar qué hace un comando antes de ejecutarlo.”””
r = claude.messages.create(
model=“claude-haiku-4-5”,
max_tokens=300,
messages=[{
“role”: “user”,
“content”: f”Explica en 2-3 líneas qué hace este comando bash y si es seguro ejecutarlo:\n`{cmd}`\nSé directo y menciona cualquier riesgo.”
}]
)
return r.content[0].text.strip()

def ejecutar_comando(cmd: str) -> str:
“”“Ejecuta un comando en el servidor y retorna el output.”””
try:
result = subprocess.run(
cmd, shell=True, capture_output=True, text=True, timeout=30
)
out = result.stdout + result.stderr
return out.strip()[:3000] if out.strip() else “✅ Ejecutado sin output.”
except subprocess.TimeoutExpired:
return “⏱ Timeout: el comando tardó más de 30s”
except Exception as e:
return f”❌ Error: {e}”

# ══════════════════════════════════════════════

# BLOQUE 5 — API n8n

# ══════════════════════════════════════════════

def n8n_headers():
return {
“X-N8N-API-KEY”: N8N_API_KEY,
“Content-Type”: “application/json”
}

def normalizar_workflow(wf: dict) -> dict:
“”“Limpia el JSON para que n8n lo acepte al importar.”””
wf.pop(“id”, None)
wf.pop(“active”, None)
wf.pop(“createdAt”, None)
wf.pop(“updatedAt”, None)
wf.pop(“versionId”, None)

```
wf.setdefault("settings", {"executionOrder": "v1"})
wf.setdefault("pinData", {})
wf.setdefault("connections", {})

for node in wf.get("nodes", []):
    node.setdefault("parameters", {})
    node.setdefault("position", [300, 300])
    node.setdefault("typeVersion", 1)
    if not node.get("id"):
        node["id"] = f"node_{node['name'].replace(' ', '_').lower()}"

return wf
```

def crear_workflow_n8n(wf: dict) -> dict:
wf = normalizar_workflow(wf)
r = requests.post(
f”{N8N_URL}/api/v1/workflows”,
headers=n8n_headers(),
json=wf,
timeout=15
)
try:
return r.json()
except:
return {“error”: r.text, “status”: r.status_code}

def listar_workflows_n8n() -> list:
r = requests.get(
f”{N8N_URL}/api/v1/workflows”,
headers=n8n_headers(),
timeout=10
)
try:
data = r.json()
return data.get(“data”, data) if isinstance(data, dict) else data
except:
return []

def obtener_workflow_n8n(wf_id: str) -> dict:
r = requests.get(
f”{N8N_URL}/api/v1/workflows/{wf_id}”,
headers=n8n_headers(),
timeout=10
)
try:
return r.json()
except:
return {}

def actualizar_workflow_n8n(wf_id: str, wf: dict) -> dict:
wf = normalizar_workflow(wf)
r = requests.put(
f”{N8N_URL}/api/v1/workflows/{wf_id}”,
headers=n8n_headers(),
json=wf,
timeout=15
)
try:
return r.json()
except:
return {“error”: r.text}

def activar_workflow_n8n(wf_id: str, activar: bool) -> dict:
endpoint = “activate” if activar else “deactivate”
r = requests.post(
f”{N8N_URL}/api/v1/workflows/{wf_id}/{endpoint}”,
headers=n8n_headers(),
timeout=10
)
try:
return r.json()
except:
return {“error”: r.text}

# ══════════════════════════════════════════════

# BLOQUE 6 — HANDLERS TELEGRAM

# ══════════════════════════════════════════════

async def handle_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
“”“Handler principal — clasifica y responde.”””
uid = update.effective_user.id
if uid != ALLOWED_USER:
return

```
texto = update.message.text
st = get_estado(uid)
chat_id = update.effective_chat.id

# Indicador de escritura
await context.bot.send_chat_action(chat_id, "typing")

# ── Clasificar intención ──
await update.message.reply_text("🧠 Analizando...")
intencion = await clasificar_intencion(texto)
tipo = intencion.get("tipo", "OTRO")
datos = intencion.get("datos", {})

# ── Guardar en historial ──
st["historial"].append({"role": "user", "content": texto})

# ─────────────────────────────────────────
# FLUJO: CREAR
# ─────────────────────────────────────────
if tipo == "FLUJO_CREAR":
    await update.message.reply_text(
        f"🏗 Generando flujo: *{datos.get('nombre', 'Nuevo workflow')}*\n"
        f"_{datos.get('descripcion', texto)}_",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id, "typing")
    
    try:
        wf = await generar_flujo_ia(texto)
        st["flujo"] = wf
        st["flujo_descripcion"] = texto
        
        preview = f"*{wf.get('name', 'Workflow')}*\n"
        preview += f"📦 Nodos: {len(wf.get('nodes', []))}\n"
        preview += "Nodos incluidos:\n"
        for n in wf.get("nodes", []):
            preview += f"  • {n.get('name')} ({n.get('type','').split('.')[-1]})\n"
        
        kb = [
            [
                InlineKeyboardButton("🚀 Crear en n8n", callback_data="flujo_crear"),
                InlineKeyboardButton("📄 Ver JSON",     callback_data="flujo_ver_json"),
            ],
            [
                InlineKeyboardButton("🔄 Regenerar",    callback_data="flujo_regen"),
                InlineKeyboardButton("✏️ Modificar",    callback_data="flujo_modificar"),
            ]
        ]
        
        await update.message.reply_text(
            f"✅ Flujo listo:\n{preview}",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando flujo: {e}")

# ─────────────────────────────────────────
# FLUJO: REPARAR
# ─────────────────────────────────────────
elif tipo == "FLUJO_REPARAR":
    flujos = listar_workflows_n8n()
    if not flujos:
        await update.message.reply_text("⚠️ No encontré flujos en n8n.")
        return
    
    # Mostrar lista para que elija cuál reparar
    kb = []
    for f in flujos[:10]:
        wf_id = f.get("id", "")
        nombre = f.get("name", f"Workflow {wf_id}")
        kb.append([InlineKeyboardButton(
            f"🔧 {nombre}",
            callback_data=f"reparar_{wf_id}"
        )])
    
    st["repair_descripcion"] = texto
    
    await update.message.reply_text(
        "🔧 ¿Cuál flujo quieres reparar?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ─────────────────────────────────────────
# FLUJO: LISTAR
# ─────────────────────────────────────────
elif tipo == "FLUJO_LISTAR":
    flujos = listar_workflows_n8n()
    if not flujos:
        await update.message.reply_text("📭 No hay flujos en n8n todavía.")
        return
    
    msg = "📋 *Flujos en n8n:*\n\n"
    kb = []
    for f in flujos:
        wf_id = f.get("id", "")
        nombre = f.get("name", "Sin nombre")
        activo = "🟢" if f.get("active") else "🔴"
        msg += f"{activo} `{wf_id}` — *{nombre}*\n"
        kb.append([
            InlineKeyboardButton(f"👁 {nombre}", callback_data=f"ver_{wf_id}"),
            InlineKeyboardButton("⚡ Toggle",    callback_data=f"toggle_{wf_id}_{str(not f.get('active')).lower()}")
        ])
    
    await update.message.reply_text(
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ─────────────────────────────────────────
# COMANDO DE SISTEMA
# ─────────────────────────────────────────
elif tipo == "CMD_SISTEMA":
    cmd = datos.get("cmd_sugerido", "")
    
    if not cmd:
        # Pedir al modelo que sugiera el comando
        r = claude.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": f"Dame SOLO el comando bash para: {texto}\nSin explicación, solo el comando."
            }]
        )
        cmd = r.content[0].text.strip().strip("`")
    
    st["cmd"] = cmd
    explicacion = await explicar_comando(cmd)
    
    kb = [
        [
            InlineKeyboardButton("✅ Ejecutar", callback_data="cmd_ejecutar"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cmd_cancelar"),
        ],
        [
            InlineKeyboardButton("🔍 Explicar más", callback_data="cmd_explicar"),
        ]
    ]
    
    await update.message.reply_text(
        f"⚡ *Comando detectado:*\n`{cmd}`\n\n"
        f"📖 *Qué hace:*\n{explicacion}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

# ─────────────────────────────────────────
# PREGUNTA / CONVERSACIÓN
# ─────────────────────────────────────────
else:
    await context.bot.send_chat_action(chat_id, "typing")
    resp = await respuesta_general(texto, st["historial"])
    st["historial"].append({"role": "assistant", "content": resp})
    await update.message.reply_text(resp)
```

# ══════════════════════════════════════════════

# BLOQUE 7 — CALLBACK BUTTONS

# ══════════════════════════════════════════════

async def handle_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
query = update.callback_query
await query.answer()

```
uid   = query.from_user.id
cdata = query.data
chat  = query.message.chat.id
st    = get_estado(uid)

# ── FLUJOS ──────────────────────────────
if cdata == "flujo_crear":
    if not st.get("flujo"):
        await context.bot.send_message(chat, "❌ No hay flujo en memoria.")
        return
    await context.bot.send_message(chat, "🚀 Enviando a n8n...")
    res = crear_workflow_n8n(st["flujo"])
    wf_id = res.get("id", "")
    nombre = res.get("name", "")
    if wf_id:
        await context.bot.send_message(
            chat,
            f"✅ *Flujo creado exitosamente!*\n"
            f"📛 Nombre: {nombre}\n"
            f"🆔 ID: `{wf_id}`\n"
            f"🔗 {N8N_URL}/workflow/{wf_id}",
            parse_mode="Markdown"
        )
    else:
        await context.bot.send_message(chat, f"❌ Error: {res}")

elif cdata == "flujo_ver_json":
    if not st.get("flujo"):
        await context.bot.send_message(chat, "❌ No hay flujo en memoria.")
        return
    txt = json.dumps(st["flujo"], indent=2, ensure_ascii=False)
    # Telegram tiene límite de 4096 chars por mensaje
    for i in range(0, len(txt), 3800):
        chunk = txt[i:i+3800]
        await context.bot.send_message(
            chat, f"```json\n{chunk}\n```", parse_mode="Markdown"
        )

elif cdata == "flujo_regen":
    desc = st.get("flujo_descripcion", "flujo genérico")
    await context.bot.send_message(chat, "🔄 Regenerando con IA...")
    try:
        wf = await generar_flujo_ia(desc)
        st["flujo"] = wf
        preview = f"✅ Regenerado: *{wf.get('name')}*\n📦 {len(wf.get('nodes',[]))} nodos"
        kb = [[
            InlineKeyboardButton("🚀 Crear en n8n", callback_data="flujo_crear"),
            InlineKeyboardButton("📄 Ver JSON",     callback_data="flujo_ver_json"),
        ]]
        await context.bot.send_message(
            chat, preview,
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
    except Exception as e:
        await context.bot.send_message(chat, f"❌ Error: {e}")

elif cdata == "flujo_modificar":
    await context.bot.send_message(
        chat,
        "✏️ Dime qué quieres cambiar del flujo actual.\n"
        "Ejemplo: _'Agrega un nodo de WhatsApp para notificar al dueño'_",
        parse_mode="Markdown"
    )
    st["modo"] = "modificar"

# ── REPARAR ─────────────────────────────
elif cdata.startswith("reparar_"):
    wf_id = cdata.replace("reparar_", "")
    await context.bot.send_message(chat, f"🔍 Obteniendo flujo `{wf_id}`...", parse_mode="Markdown")
    
    flujo_actual = obtener_workflow_n8n(wf_id)
    if not flujo_actual:
        await context.bot.send_message(chat, "❌ No pude obtener el flujo.")
        return
    
    desc = st.get("repair_descripcion", "Revisa y repara todos los errores posibles")
    await context.bot.send_message(chat, "🔧 Reparando con IA...")
    
    try:
        flujo_reparado = await generar_flujo_ia(desc, flujo_actual)
        st["flujo"] = flujo_reparado
        st["repair_id"] = wf_id
        
        kb = [[
            InlineKeyboardButton("💾 Guardar reparación", callback_data="flujo_guardar_reparacion"),
            InlineKeyboardButton("📄 Ver JSON",            callback_data="flujo_ver_json"),
        ]]
        await context.bot.send_message(
            chat,
            f"✅ Flujo reparado: *{flujo_reparado.get('name')}*\n"
            f"¿Guardarlo en n8n?",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
    except Exception as e:
        await context.bot.send_message(chat, f"❌ Error reparando: {e}")

elif cdata == "flujo_guardar_reparacion":
    wf_id = st.get("repair_id")
    if not wf_id or not st.get("flujo"):
        await context.bot.send_message(chat, "❌ Sin datos de reparación.")
        return
    res = actualizar_workflow_n8n(wf_id, st["flujo"])
    if res.get("id"):
        await context.bot.send_message(chat, f"✅ Flujo `{wf_id}` actualizado correctamente!", parse_mode="Markdown")
    else:
        await context.bot.send_message(chat, f"❌ Error guardando: {res}")

# ── VER FLUJO ────────────────────────────
elif cdata.startswith("ver_"):
    wf_id = cdata.replace("ver_", "")
    flujo = obtener_workflow_n8n(wf_id)
    if flujo:
        info = (
            f"📋 *{flujo.get('name')}*\n"
            f"🆔 ID: `{wf_id}`\n"
            f"📦 Nodos: {len(flujo.get('nodes',[]))}\n"
            f"🟢 Activo: {flujo.get('active', False)}\n"
        )
        for n in flujo.get("nodes", []):
            info += f"  • {n.get('name')}\n"
        
        kb = [[
            InlineKeyboardButton("🔧 Reparar este flujo", callback_data=f"reparar_{wf_id}"),
            InlineKeyboardButton("📄 Ver JSON",            callback_data=f"json_{wf_id}"),
        ]]
        await context.bot.send_message(
            chat, info, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )

elif cdata.startswith("json_"):
    wf_id = cdata.replace("json_", "")
    flujo = obtener_workflow_n8n(wf_id)
    if flujo:
        txt = json.dumps(flujo, indent=2, ensure_ascii=False)
        for i in range(0, min(len(txt), 7600), 3800):
            await context.bot.send_message(
                chat, f"```json\n{txt[i:i+3800]}\n```", parse_mode="Markdown"
            )

# ── TOGGLE ACTIVO/INACTIVO ───────────────
elif cdata.startswith("toggle_"):
    parts = cdata.split("_")
    wf_id   = parts[1]
    activar = parts[2] == "true"
    res = activar_workflow_n8n(wf_id, activar)
    estado_str = "activado 🟢" if activar else "desactivado 🔴"
    await context.bot.send_message(
        chat,
        f"{'✅' if res.get('id') else '❌'} Flujo `{wf_id}` {estado_str}",
        parse_mode="Markdown"
    )

# ── COMANDOS DE SISTEMA ──────────────────
elif cdata == "cmd_ejecutar":
    cmd = st.get("cmd")
    if not cmd:
        await context.bot.send_message(chat, "❌ No hay comando en memoria.")
        return
    await context.bot.send_message(chat, f"⚡ Ejecutando: `{cmd}`", parse_mode="Markdown")
    output = ejecutar_comando(cmd)
    await context.bot.send_message(chat, f"```\n{output[:3800]}\n```", parse_mode="Markdown")

elif cdata == "cmd_cancelar":
    st["cmd"] = None
    await context.bot.send_message(chat, "❌ Comando cancelado.")

elif cdata == "cmd_explicar":
    cmd = st.get("cmd", "")
    if cmd:
        exp = await explicar_comando(cmd)
        # Más detalle
        r = claude.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"Explica en detalle, paso a paso, qué hace este comando bash en Ubuntu, sus flags y posibles efectos:\n`{cmd}`"
            }]
        )
        detalle = r.content[0].text.strip()
        await context.bot.send_message(chat, f"🔍 *Detalle del comando:*\n\n{detalle}", parse_mode="Markdown")
```

# ══════════════════════════════════════════════

# BLOQUE 8 — COMANDO /start Y /help

# ══════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
await update.message.reply_text(
“⚡ *CLAW CORE* — Tu asistente n8n\n\n”
“Puedes pedirme:\n”
“🏗 *Crear flujos* — ‘Crea un flujo para tomar pedidos en WhatsApp’\n”
“🔧 *Reparar flujos* — ‘Repara el flujo que está fallando’\n”
“📋 *Listar flujos* — ‘Muéstrame mis flujos en n8n’\n”
“⚡ *Comandos* — ‘Cuánta memoria queda en la BMAX’\n”
“💬 *Preguntas* — ‘Qué precio le pongo al flujo de reservas’\n\n”
“Simplemente escríbeme en lenguaje natural 🤙”,
parse_mode=“Markdown”
)

async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
flujos = listar_workflows_n8n()
activos = sum(1 for f in flujos if f.get(“active”))
await update.message.reply_text(
f”📊 *Estado del sistema:*\n”
f”🌐 n8n: {‘✅ Online’ if flujos is not None else ‘❌ Offline’}\n”
f”📦 Flujos totales: {len(flujos)}\n”
f”🟢 Activos: {activos}\n”
f”🔴 Inactivos: {len(flujos) - activos}”,
parse_mode=“Markdown”
)

# ══════════════════════════════════════════════

# MAIN

# ══════════════════════════════════════════════

def main():
print(“🔥 CLAW CORE iniciando…”)

```
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", cmd_start))
app.add_handler(CommandHandler("estado", cmd_estado))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mensaje))
app.add_handler(CallbackQueryHandler(handle_botones))

print("✅ Bot listo — esperando mensajes")
app.run_polling(drop_pending_updates=True)
```

if **name** == “**main**”:
main()
