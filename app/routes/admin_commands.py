import json
import re
import json
import re
import os
import shutil
import base64
from datetime import datetime
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from app.core.database import get_db_connection

router = APIRouter(tags=["admin_commands"])
templates = Jinja2Templates(directory="app/templates")

IMAGES_DIR = "static/commands/images"
SOUNDS_DIR = "static/commands/sounds"
ALLOWED_IMAGES = {".gif", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"}
ALLOWED_SOUNDS  = {".mp3", ".wav", ".ogg"}

VARIABLES_HELP = [
    ("{username}",  "Pseudo Twitch du viewer"),
    ("{level}",     "Niveau du viewer"),
    ("{points}",    "Points EXP du viewer"),
    ("{date}",      "Date du jour"),
    ("{time}",      "Heure actuelle"),
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _list_files(folder: str, allowed: set) -> list[str]:
    if not os.path.exists(folder):
        return []
    return sorted(f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in allowed)

def _resolve_variables(text: str, username="AdminTest", level=99, points=13370) -> str:
    now = datetime.now()
    return (text
        .replace("{username}", username)
        .replace("{level}",   str(level))
        .replace("{points}",  str(points))
        .replace("{date}",    now.strftime("%d/%m/%Y"))
        .replace("{time}",    now.strftime("%H:%M"))
    )

def _safe_name(name: str) -> str:
    return name.lower().replace("!", "").strip()


# ─── Page admin ───────────────────────────────────────────────────────────────

@router.get("/admin/commands", response_class=HTMLResponse)
async def admin_commands_page(request: Request):
    async with get_db_connection() as conn:
        c = await conn.execute("SELECT * FROM custom_commands ORDER BY name ASC")
        rows = await c.fetchall()
    commands = [dict(r) for r in rows]
    return templates.TemplateResponse(request=request, name="admin/commands_manager.html", context={
        "request":  request,
        "commands": commands,
        "images":   _list_files(IMAGES_DIR, ALLOWED_IMAGES),
        "sounds":   _list_files(SOUNDS_DIR, ALLOWED_SOUNDS),
        "variables": VARIABLES_HELP,
    })


# ─── CRUD via API JSON (utilisé par le JS de la page) ─────────────────────────

@router.get("/api/admin/commands")
async def api_get_commands():
    try:
        async with get_db_connection() as conn:
            c = await conn.execute("SELECT * FROM custom_commands ORDER BY name ASC")
            rows = await c.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/admin/commands")
async def api_save_command(request: Request):
    try:
        data = await request.json()
        name = _safe_name(data["name"])
        
        # On regroupe les alias dans une simple chaîne de texte (ex: "rs,sociaux")
        aliases_str = ",".join([_safe_name(a) for a in data.get("aliases", [])])
        
        category = data.get("category", "Général").strip() or "Général"
        
        response_payload = {
            "text": data.get("text_response", ""),
            "image": data.get("image_file", ""),
            "sound": data.get("sound_file", ""),
            "obs": data.get("obs_data", {})
        }
        
        async with get_db_connection() as conn:
            await conn.execute("""
                INSERT INTO custom_commands
                    (name, aliases, type, response, chat_response, cooldown_global, cooldown_user,
                     min_role, is_active, active_from, active_until, created_by, category)
                VALUES ($1,$2,$3,$4,NULL,$5,$6,$7,$8,$9,$10,'admin',$11)
                ON CONFLICT (name) DO UPDATE SET
                    aliases        = EXCLUDED.aliases,
                    type           = EXCLUDED.type,
                    response       = EXCLUDED.response,
                    cooldown_global= EXCLUDED.cooldown_global,
                    cooldown_user  = EXCLUDED.cooldown_user,
                    min_role       = EXCLUDED.min_role,
                    is_active      = EXCLUDED.is_active,
                    active_from    = EXCLUDED.active_from,
                    active_until   = EXCLUDED.active_until,
                    category       = EXCLUDED.category,
                    updated_at     = NOW()
            """, (name, aliases_str, 'multi', json.dumps(response_payload),
                  int(data.get("cooldown_global", 10)),
                  int(data.get("cooldown_user", 30)),
                  data.get("min_role", "viewer"),
                  bool(data.get("is_active", True)),
                  data.get("active_from") or None,
                  data.get("active_until") or None,
                  category))
        return {"status": "ok", "name": name}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/api/admin/commands/toggle/{name}")
async def api_toggle_command(name: str):
    try:
        async with get_db_connection() as conn:
            await conn.execute(
                "UPDATE custom_commands SET is_active = NOT is_active WHERE name=$1", (_safe_name(name),))
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.delete("/api/admin/commands/{name}")
async def api_delete_command(name: str):
    try:
        async with get_db_connection() as conn:
            await conn.execute("DELETE FROM custom_commands WHERE name=$1", (_safe_name(name),))
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Test d'une commande ──────────────────────────────────────────────────────

@router.post("/api/admin/commands/test/{name}")
async def api_test_command(name: str):
    try:
        async with get_db_connection() as conn:
            c = await conn.execute(
                "SELECT * FROM custom_commands WHERE name=$1", (_safe_name(name),))
            row = await c.fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Commande introuvable"})
        cmd = dict(row)
        return {
            "status":  "ok",
            "type":    cmd["type"],
            "response": _resolve_variables(cmd["response"] or ""),
            "chat":    _resolve_variables(cmd.get("chat_response") or ""),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Upload & gestion des médias ─────────────────────────────────────────────

@router.post("/api/admin/commands/upload/{media_type}")
async def api_upload_media(media_type: str, file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if media_type == "image" and ext not in ALLOWED_IMAGES:
        return JSONResponse(status_code=400, content={"error": f"Format non supporté : {ext}"})
    if media_type == "sound" and ext not in ALLOWED_SOUNDS:
        return JSONResponse(status_code=400, content={"error": f"Format non supporté : {ext}"})
    folder = IMAGES_DIR if media_type == "image" else SOUNDS_DIR
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, file.filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"status": "ok", "filename": file.filename}


@router.get("/api/admin/commands/media/{media_type}")
async def api_list_media(media_type: str):
    folder  = IMAGES_DIR if media_type == "image" else SOUNDS_DIR
    allowed = ALLOWED_IMAGES if media_type == "image" else ALLOWED_SOUNDS
    return {"files": _list_files(folder, allowed)}


@router.delete("/api/admin/commands/media/{media_type}/{filename}")
async def api_delete_media(media_type: str, filename: str):
    folder = IMAGES_DIR if media_type == "image" else SOUNDS_DIR
    path   = os.path.join(folder, filename)
    if os.path.exists(path):
        os.remove(path)
        return {"status": "ok"}
    return JSONResponse(status_code=404, content={"error": "Fichier introuvable"})


# ─── Import Streamer.bot ──────────────────────────────────────────────────────

@router.get("/admin/commands/import", response_class=HTMLResponse)
async def import_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/import_streamerbot.html", context={"request": request})


@router.post("/api/admin/commands/import/parse")
async def parse_streamerbot(file: UploadFile = File(...)):
    """Parse le fichier export Streamer.bot et prépare l'import Multi-Actions."""
    import gzip, re

    raw = await file.read()

    # Décoder base64 si nécessaire
    try:
        decoded = base64.b64decode(raw)
    except Exception:
        decoded = raw

    # Strip header SBAE et décompresser gzip
    if decoded[:4] == b'SBAE':
        decoded = gzip.decompress(decoded[4:])
    elif decoded[:2] == b'\x1f\x8b':
        decoded = gzip.decompress(decoded)

    data = json.loads(decoded)
    commands    = data['data']['commands']
    actions_raw = data['data']['actions']
    actions_by_name = {}
    for a in actions_raw:
        key = a['name'].lower().strip()
        actions_by_name[key] = a
        clean = re.sub(r'\(.*?\)', '', a['name']).lower().strip()
        actions_by_name[clean] = a

    ROLE_MAP = {0:'viewer', 1:'mod', 2:'admin', 3:'vip', 4:'sub'}

    def get_texts(action):
        texts = []
        for sub in action.get('subActions', []):
            # C'est ICI qu'était l'erreur : Streamer.bot utilise "message" et non "text" !
            msg = sub.get('message') or sub.get('text')
            if msg and sub.get('type') in (1, 10, 23):
                texts.append(msg)
        return texts

    def get_sounds(action):
        sounds = []
        for sub in action.get('subActions', []):
            sf = sub.get('soundFile', '')
            if sf:
                # On ne garde que le nom exact du fichier (ex: 'Attends attends.mp3')
                sounds.append(sf.replace('\\', '/').split('/')[-1])
        return sounds

    def get_obs(action):
        for sub in action.get('subActions', []):
            if sub.get('type') == 30:
                state = sub.get('state', 0)
                return {'action': 'source_show' if state==0 else 'source_hide' if state==1 else 'source_toggle',
                        'scene': sub.get('sceneName',''), 'source': sub.get('sourceName','')}
        return {}

    def convert_vars(text):
        if not text: return text
        return (text.replace('%userName%','{username}').replace('%username%','{username}')
                    .replace('%user%','{username}').replace('%rawInput%','{input}')
                    .replace('%rawinput%','{input}').replace('%input0%','{input}')
                    .replace('%followDate%','{follow_date}').replace('%gameName%','{game}'))

    def get_primary(cmd):
        return cmd.get('command','').split('\n')[0].strip().lstrip('!').lower()

    def get_aliases(cmd):
        parts = [p.strip().lstrip('!') for p in cmd.get('command','').split('\n') if p.strip()]
        return [p.lower() for p in parts[1:]] if len(parts) > 1 else []

    ready = []
    review = []
    moderation = []
    translate = []
    games = []

    for cmd in commands:
        primary = get_primary(cmd)
        aliases  = get_aliases(cmd)
        group    = cmd.get('group', 'Général')
        role     = ROLE_MAP.get(cmd.get('grantType', 0), 'viewer')
        cg       = cmd.get('globalCooldown', 10)
        cu       = cmd.get('userCooldown', 30)

        if any(x in group for x in ['Modo', 'Chat Mode']):
            moderation.append({'name': primary, 'aliases': aliases})
            continue
        if 'GAME' in group.upper():
            games.append({'name': primary, 'aliases': aliases})
            continue
        if 'Translate' in group or 'translate' in cmd.get('name','').lower():
            translate.append({'name': primary, 'aliases': aliases})
            continue

        action = actions_by_name.get(cmd.get('name','').lower().strip())
        if not action:
            review.append({'name': primary, 'aliases': aliases, 'reason': 'Action non trouvée'})
            continue

        texts  = get_texts(action)
        sounds = get_sounds(action)
        obs_data = get_obs(action)

        chat_msg = convert_vars(texts[0]) if texts else ""
        sound_file = sounds[0] if sounds else ""

        # On regroupe TOUT dans un seul JSON "Multi-actions"
        if chat_msg or sound_file or obs_data:
            payload = {
                "text": chat_msg,
                "image": "",
                "sound": sound_file,
                "obs": obs_data
            }
            ready.append({
                'name': primary, 
                'aliases': aliases, 
                'category': group,
                'response': json.dumps(payload),
                'cooldown_global': cg, 
                'cooldown_user': cu, 
                'min_role': role
            })
        else:
            review.append({'name': primary, 'aliases': aliases, 'reason': 'Action vide ou C# uniquement'})

    return {"ready": ready, "review": review, "moderation": moderation,
            "translate": translate, "games": games}


@router.post("/api/admin/commands/import/execute")
async def execute_import(request: Request):
    """Importe les commandes sélectionnées en DB au format Multi-Actions sans faire de doublons."""
    body = await request.json()
    commands = body.get('commands', [])
    imported = 0
    skipped  = 0
    errors   = []

    for cmd in commands:
        name = (cmd.get('name') or '').lower().strip()
        if not name:
            continue
        category = cmd.get('category', 'Général')
        
        # 👉 On regroupe tous les alias dans un seul texte (ex: "cmde,command")
        aliases_list = [a.lower().strip() for a in cmd.get('aliases', []) if a.lower().strip() and a.lower().strip() != name]
        aliases_str = ",".join(aliases_list)

        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT id FROM custom_commands WHERE name=$1", (name,))
                exists = await c.fetchone()
                if exists:
                    skipped += 1
                    continue
                
                # 👉 On insère UNE SEULE ligne qui contient le nom principal ET la colonne aliases
                await conn.execute("""
                    INSERT INTO custom_commands
                        (name, aliases, type, response, chat_response, cooldown_global,
                         cooldown_user, min_role, is_active, created_by, category)
                    VALUES ($1, $2, 'multi', $3, NULL, $4, $5, $6, FALSE, 'streamerbot_import', $7)
                """, (name, aliases_str, cmd.get('response','{}'),
                      int(cmd.get('cooldown_global', 10)),
                      int(cmd.get('cooldown_user', 30)),
                      cmd.get('min_role','viewer'), category))
                imported += 1
                
        except Exception as e:
            errors.append(f"{name}: {str(e)[:50]}")

    return {"imported": imported, "skipped": skipped, "errors": errors}

@router.get("/api/admin/sounds")
async def list_available_sounds():
    """Renvoie la liste des fichiers audio déjà uploadés dans le dossier du bot."""
    # Ajuste ce chemin selon l'emplacement réel de tes sons dans ton dossier CORE ou STATIC
    sound_dir = "/home/thomas/masthom/BOT_V2/static/commands/sounds"
    
    if not os.path.exists(sound_dir):
        return {"sounds": []}
        
    # Ne garder que les fichiers audio
    valid_extensions = ('.mp3', '.wav', '.ogg')
    files = [f for f in os.listdir(sound_dir) if f.lower().endswith(valid_extensions)]
    
    return {"sounds": sorted(files)}
