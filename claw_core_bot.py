import os, json, subprocess, requests
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
ApplicationBuilder, MessageHandler, CommandHandler,
ContextTypes, CallbackQueryHandler, filters,
)

load_dotenv(”/home/mau/claw_core/.env”)

TELEGRAM_TOKEN = os.getenv(“TELEGRAM_TOKEN”)
ALLOWED_USER   = int(os.getenv(“ALLOWED_USER”, “0”))
N8N_URL        = os.getenv(“N8N_URL”, “http://localhost:5678”)
N8N_API_KEY    = os.getenv(“N8N_API_KEY”)
OPENROUTER_KEY = os.getenv(“OPENROUTER_API_KEY”)

MODELO = “anthropic/claude-3-haiku”

client = OpenAI(
api_key=OPENROUTER_KEY,
base_url=“https://openrouter.ai/api/v1”,
)

estado = {}

def get_st(uid):
if uid not in estado:
estado[uid] = {
“flujo”: None, “cmd”: None, “historial”: [],
“repair_id”: None, “flujo_desc”: “”, “repair_desc”: “”, “modo”: None,
}
return estado[uid]

def or_chat(system, messages, max_tokens=600):
msgs = [{“role”: “system”, “content”: system}] + messages
r = client.chat.completions.create(
model=MODELO,
max_tokens=max_tokens,
messages=msgs,
extra_headers={
“HTTP-Referer”: “https://github.com/claw-core”,
“X-Title”: “CLAW CORE Bot”,
},
)
return r.choices[0].message.content.strip()

SYS_CLAS = “”“Clasifica el mensaje. Responde SOLO JSON valido, sin markdown ni texto extra.
{“tipo”:”<TIPO>”,“resumen”:”<que pide>”,“datos”:{}}
Tipos:
FLUJO_CREAR   - quiere crear un workflow nuevo en n8n
FLUJO_REPARAR - quiere arreglar un flujo existente
FLUJO_LISTAR  - quiere ver sus flujos en n8n
CMD_SISTEMA   - quiere ejecutar algo en el servidor Ubuntu
PREGUNTA      - pregunta sobre n8n, precios, negocio
OTRO          - cualquier otra cosa
Para CMD_SISTEMA: {“datos”:{“cmd_sugerido”:”<comando bash exacto>”}}
Para FLUJO_CREAR: {“datos”:{“nombre”:”<nombre>”,“descripcion”:”<descripcion>”}}”””

def clasificar(texto):
try:
raw = or_chat(SYS_CLAS, [{“role”: “user”, “content”: texto}], max_tokens=300)
if “`" in raw: raw = raw.split("`”)[1].lstrip(“json”).strip()
return json.loads(raw)
except Exception as e:
print(f”[clasificar error] {e}”)
return {“tipo”: “OTRO”, “resumen”: texto, “datos”: {}}

SYS_N8N = “”“Eres experto en n8n. Genera workflows JSON validos e importables directamente.
REGLAS:

- Devuelve SOLO el JSON, sin markdown, sin texto extra
- Campos root obligatorios: name, nodes, connections, settings, pinData
- Cada nodo debe tener: id (string unico), name, type, typeVersion, position ([x,y]), parameters
- Posiciones: X empieza en 200 e incrementa 250 por nodo. Y base 300
- Nodos reales: n8n-nodes-base.webhook, n8n-nodes-base.httpRequest,
  n8n-nodes-base.googleSheets, n8n-nodes-base.set, n8n-nodes-base.if,
  n8n-nodes-base.sendEmail, n8n-nodes-base.respondToWebhook
- Conexiones: {“NodoA”:{“main”:[[{“node”:“NodoB”,“type”:“main”,“index”:0}]]}}
- settings: {“executionOrder”:“v1”}
- Flujos COMPLETOS y FUNCIONALES, listos para vender a negocios.”””

def generar_flujo(descripcion, flujo_base=None):
if flujo_base:
prompt = (
f”Repara este flujo n8n:\n{json.dumps(flujo_base, indent=2)}\n\n”
f”Problema:\n{descripcion}\n\nDevuelve el JSON completo corregido.”
)
else:
prompt = f”Crea un workflow n8n completo para:\n{descripcion}\nDevuelve SOLO el JSON.”
raw = or_chat(SYS_N8N, [{“role”: “user”, “content”: prompt}], max_tokens=4000)
if “`" in raw: raw = raw.split("`”)[1].lstrip(“json”).strip()
return json.loads(raw)

SYS_ASIST = “”“Eres CLAW CORE, asistente de Mau. Experto en n8n y automatizaciones.
Mau vende flujos n8n a restaurantes y negocios. Responde en espanol, directo y practico.”””

def respuesta_general(texto, historial):
msgs = historial[-8:] + [{“role”: “user”, “content”: texto}]
return or_chat(SYS_ASIST, msgs, max_tokens=800)

def explicar_cmd(cmd):
return or_chat(
“Explica comandos bash de forma corta.”,
[{“role”: “user”, “content”: f”Explica en 2 lineas que hace este comando y si es seguro:\n`{cmd}`”}],
max_tokens=150,
)

def ejecutar_cmd(cmd):
try:
res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
out = (res.stdout + res.stderr).strip()
return out[:3000] if out else “Ejecutado sin output.”
except subprocess.TimeoutExpired:
return “Timeout: el comando tardo mas de 30s”
except Exception as e:
return f”Error: {e}”

def hdrs():
return {“X-N8N-API-KEY”: N8N_API_KEY, “Content-Type”: “application/json”}

def normalizar(wf):
for k in [“id”, “active”, “createdAt”, “updatedAt”, “versionId”]:
wf.pop(k, None)
wf.setdefault(“settings”, {“executionOrder”: “v1”})
wf.setdefault(“pinData”, {})
wf.setdefault(“connections”, {})
for n in wf.get(“nodes”, []):
n.setdefault(“parameters”, {})
n.setdefault(“position”, [300, 300])
n.setdefault(“typeVersion”, 1)
if not n.get(“id”):
n[“id”] = n.get(“name”, “node”).replace(” “, “_”).lower()
return wf

def n8n_crear(wf):
wf = normalizar(wf)
r = requests.post(f”{N8N_URL}/api/v1/workflows”, headers=hdrs(), json=wf, timeout=15)
try: return r.json()
except: return {“error”: r.text}

def n8n_listar():
r = requests.get(f”{N8N_URL}/api/v1/workflows”, headers=hdrs(), timeout=10)
try:
d = r.json()
return d.get(“data”, d) if isinstance(d, dict) else d
except: return []

def n8n_get(wid):
r = requests.get(f”{N8N_URL}/api/v1/workflows/{wid}”, headers=hdrs(), timeout=10)
try: return r.json()
except: return {}

def n8n_update(wid, wf):
wf = normalizar(wf)
r = requests.put(f”{N8N_URL}/api/v1/workflows/{wid}”, headers=hdrs(), json=wf, timeout=15)
try: return r.json()
except: return {“error”: r.text}

def n8n_toggle(wid, activar):
ep = “activate” if activar else “deactivate”
r = requests.post(f”{N8N_URL}/api/v1/workflows/{wid}/{ep}”, headers=hdrs(), timeout=10)
try: return r.json()
except: return {“error”: r.text}

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
uid = update.effective_user.id
if uid != ALLOWED_USER:
return

```
texto = update.message.text
st    = get_st(uid)
chat  = update.effective_chat.id

await ctx.bot.send_chat_action(chat, "typing")

if st.get("modo") == "modificar" and st.get("flujo"):
    st["modo"] = None
    await update.message.reply_text("Modificando flujo...")
    try:
        wf = generar_flujo(texto, st["flujo"])
        st["flujo"] = wf
        st["flujo_desc"] = texto
        nodos = "\n".join(f"  - {n.get('name')}" for n in wf.get("nodes", []))
        kb = [
            [InlineKeyboardButton("Crear en n8n", callback_data="f_crear"),
             InlineKeyboardButton("Ver JSON",     callback_data="f_json")],
            [InlineKeyboardButton("Regenerar",    callback_data="f_regen"),
             InlineKeyboardButton("Modificar",    callback_data="f_mod")],
        ]
        await update.message.reply_text(
            f"Modificado: *{wf.get('name')}*\n{len(wf.get('nodes',[]))} nodos:\n{nodos}",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"Error: `{e}`", parse_mode="Markdown")
    return

intent = clasificar(texto)
tipo   = intent.get("tipo", "OTRO")
datos  = intent.get("datos", {})
st["historial"].append({"role": "user", "content": texto})

if tipo == "FLUJO_CREAR":
    await update.message.reply_text(
        f"Generando: *{datos.get('nombre', 'Nuevo flujo')}*...", parse_mode="Markdown"
    )
    await ctx.bot.send_chat_action(chat, "typing")
    try:
        wf = generar_flujo(texto)
        st["flujo"] = wf
        st["flujo_desc"] = texto
        nodos = "\n".join(
            f"  - {n.get('name')} ({n.get('type','').split('.')[-1]})"
            for n in wf.get("nodes", [])
        )
        kb = [
            [InlineKeyboardButton("Crear en n8n", callback_data="f_crear"),
             InlineKeyboardButton("Ver JSON",     callback_data="f_json")],
            [InlineKeyboardButton("Regenerar",    callback_data="f_regen"),
             InlineKeyboardButton("Modificar",    callback_data="f_mod")],
        ]
        await update.message.reply_text(
            f"Flujo listo: *{wf.get('name')}*\n{len(wf.get('nodes',[]))} nodos:\n{nodos}",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"Error generando flujo:\n`{e}`", parse_mode="Markdown")

elif tipo == "FLUJO_REPARAR":
    flujos = n8n_listar()
    if not flujos:
        await update.message.reply_text("No hay flujos en n8n.")
        return
    st["repair_desc"] = texto
    kb = [
        [InlineKeyboardButton(f.get("name", "Workflow"), callback_data=f"rep_{f.get('id')}")]
        for f in flujos[:8]
    ]
    await update.message.reply_text("Cual flujo quieres reparar?", reply_markup=InlineKeyboardMarkup(kb))

elif tipo == "FLUJO_LISTAR":
    flujos = n8n_listar()
    if not flujos:
        await update.message.reply_text("No hay flujos en n8n.")
        return
    msg = "*Flujos en n8n:*\n\n"
    kb  = []
    for f in flujos:
        wid = f.get("id", ""); nom = f.get("name", "Sin nombre")
        act = "ON" if f.get("active") else "OFF"
        msg += f"[{act}] *{nom}* `{wid}`\n"
        kb.append([
            InlineKeyboardButton(f"Ver {nom}", callback_data=f"ver_{wid}"),
            InlineKeyboardButton("Toggle",     callback_data=f"tog_{wid}_{str(not f.get('active')).lower()}"),
        ])
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

elif tipo == "CMD_SISTEMA":
    cmd = datos.get("cmd_sugerido", "")
    if not cmd:
        cmd = or_chat(
            "Responde SOLO con el comando bash, sin explicacion ni markdown.",
            [{"role": "user", "content": f"Comando bash para: {texto}"}],
            max_tokens=60,
        ).strip("`")
    st["cmd"] = cmd
    exp = explicar_cmd(cmd)
    kb = [
        [InlineKeyboardButton("Ejecutar",    callback_data="cmd_run"),
         InlineKeyboardButton("Cancelar",    callback_data="cmd_no")],
        [InlineKeyboardButton("Mas detalle", callback_data="cmd_exp")],
    ]
    await update.message.reply_text(
        f"Comando:\n`{cmd}`\n\n{exp}",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown",
    )

else:
    await ctx.bot.send_chat_action(chat, "typing")
    resp = respuesta_general(texto, st["historial"])
    st["historial"].append({"role": "assistant", "content": resp})
    await update.message.reply_text(resp)
```

async def botones(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
q    = update.callback_query
await q.answer()
uid  = q.from_user.id
chat = q.message.chat.id
cd   = q.data
st   = get_st(uid)

```
if cd == "f_crear":
    if not st.get("flujo"):
        await ctx.bot.send_message(chat, "No hay flujo en memoria.")
        return
    await ctx.bot.send_message(chat, "Enviando a n8n...")
    res = n8n_crear(st["flujo"])
    wid = res.get("id", "")
    if wid:
        await ctx.bot.send_message(
            chat,
            f"Flujo creado!\nID: `{wid}`\n{N8N_URL}/workflow/{wid}",
            parse_mode="Markdown",
        )
    else:
        await ctx.bot.send_message(chat, f"Error: {res}")

elif cd == "f_json":
    if not st.get("flujo"):
        await ctx.bot.send_message(chat, "No hay flujo en memoria.")
        return
    txt = json.dumps(st["flujo"], indent=2, ensure_ascii=False)
    for i in range(0, len(txt), 3800):
        await ctx.bot.send_message(chat, f"```json\n{txt[i:i+3800]}\n```", parse_mode="Markdown")

elif cd == "f_regen":
    desc = st.get("flujo_desc", "flujo para negocio")
    await ctx.bot.send_message(chat, "Regenerando...")
    try:
        wf = generar_flujo(desc)
        st["flujo"] = wf
        kb = [
            [InlineKeyboardButton("Crear en n8n", callback_data="f_crear"),
             InlineKeyboardButton("Ver JSON",     callback_data="f_json")],
        ]
        await ctx.bot.send_message(
            chat, f"Regenerado: *{wf.get('name')}*",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown",
        )
    except Exception as e:
        await ctx.bot.send_message(chat, f"Error: {e}")

elif cd == "f_mod":
    st["modo"] = "modificar"
    await ctx.bot.send_message(chat, "Dime que quieres cambiar del flujo actual:")

elif cd.startswith("rep_") and cd != "rep_guardar":
    wid = cd[4:]
    await ctx.bot.send_message(chat, f"Obteniendo flujo `{wid}`...", parse_mode="Markdown")
    fl = n8n_get(wid)
    if not fl:
        await ctx.bot.send_message(chat, "No pude obtener el flujo.")
        return
    desc = st.get("repair_desc", "Revisa y repara todos los errores posibles")
    await ctx.bot.send_message(chat, "Reparando con IA...")
    try:
        fl_rep = generar_flujo(desc, fl)
        st["flujo"]     = fl_rep
        st["repair_id"] = wid
        kb = [
            [InlineKeyboardButton("Guardar reparacion", callback_data="rep_guardar"),
             InlineKeyboardButton("Ver JSON",           callback_data="f_json")],
        ]
        await ctx.bot.send_message(
            chat,
            f"Reparado: *{fl_rep.get('name')}*\nGuardarlo en n8n?",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown",
        )
    except Exception as e:
        await ctx.bot.send_message(chat, f"Error reparando: {e}")

elif cd == "rep_guardar":
    wid = st.get("repair_id")
    fl  = st.get("flujo")
    if not wid or not fl:
        await ctx.bot.send_message(chat, "Sin datos de reparacion.")
        return
    res = n8n_update(wid, fl)
    ok  = "OK" if res.get("id") else "Error"
    await ctx.bot.send_message(chat, f"{ok}: flujo `{wid}` actualizado", parse_mode="Markdown")

elif cd.startswith("ver_"):
    wid = cd[4:]
    fl  = n8n_get(wid)
    if fl:
        nodos = "\n".join(f"  - {n.get('name')}" for n in fl.get("nodes", []))
        kb = [
            [InlineKeyboardButton("Reparar", callback_data=f"rep_{wid}"),
             InlineKeyboardButton("JSON",    callback_data=f"js_{wid}")],
        ]
        await ctx.bot.send_message(
            chat,
            f"*{fl.get('name')}*\nID: `{wid}`\n{len(fl.get('nodes',[]))} nodos:\n{nodos}",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown",
        )

elif cd.startswith("js_"):
    fl  = n8n_get(cd[3:])
    txt = json.dumps(fl, indent=2, ensure_ascii=False) if fl else "{}"
    for i in range(0, min(len(txt), 7600), 3800):
        await ctx.bot.send_message(chat, f"```json\n{txt[i:i+3800]}\n```", parse_mode="Markdown")

elif cd.startswith("tog_"):
    parts   = cd.split("_")
    wid     = parts[1]
    activar = parts[2] == "true"
    res     = n8n_toggle(wid, activar)
    txt     = "activado" if activar else "desactivado"
    await ctx.bot.send_message(
        chat,
        f"{'OK' if res.get('id') else 'Error'}: flujo {txt}",
    )

elif cd == "cmd_run":
    cmd = st.get("cmd", "")
    if not cmd:
        await ctx.bot.send_message(chat, "Sin comando en memoria.")
        return
    await ctx.bot.send_message(chat, f"Ejecutando: `{cmd}`", parse_mode="Markdown")
    out = ejecutar_cmd(cmd)
    await ctx.bot.send_message(chat, f"```\n{out}\n```", parse_mode="Markdown")

elif cd == "cmd_no":
    st["cmd"] = None
    await ctx.bot.send_message(chat, "Comando cancelado.")

elif cd == "cmd_exp":
    cmd = st.get("cmd", "")
    if cmd:
        det = or_chat(
            "Explica comandos bash en detalle tecnico.",
            [{"role": "user", "content": f"Explica flags y efectos de:\n`{cmd}`"}],
            max_tokens=400,
        )
        await ctx.bot.send_message(chat, det)
```

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
await update.message.reply_text(
“*CLAW CORE* listo\n\n”
“Ejemplos:\n”
“- Crea un flujo de pedidos por WhatsApp para restaurante\n”
“- Repara el flujo que esta fallando\n”
“- Muestrame mis flujos en n8n\n”
“- Cuanta RAM queda en la BMAX\n”
“- A que precio vendo el flujo de reservas\n\n”
“/estado - estado del sistema”,
parse_mode=“Markdown”,
)

async def cmd_estado(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ALLOWED_USER:
return
flujos = n8n_listar()
act    = sum(1 for f in flujos if f.get(“active”))
ram    = ejecutar_cmd(“free -h | awk ‘/^Mem/{print $3"/"$2}’”)
disco  = ejecutar_cmd(“df -h / | awk ‘NR==2{print $3"/"$2}’”)
await update.message.reply_text(
f”*Sistema:*\n”
f”n8n: {‘OK’ if flujos is not None else ‘Sin conexion’}\n”
f”Flujos: {len(flujos)} ({act} activos)\n”
f”RAM: {ram}\n”
f”Disco: {disco}\n”
f”Modelo: {MODELO}”,
parse_mode=“Markdown”,
)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler(“start”,  cmd_start))
app.add_handler(CommandHandler(“estado”, cmd_estado))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CallbackQueryHandler(botones))

print(f”CLAW CORE activo | modelo: {MODELO} | usuario: {ALLOWED_USER}”)
app.run_polling(drop_pending_updates=True)
