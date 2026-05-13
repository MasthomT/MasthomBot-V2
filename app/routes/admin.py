import os
import sqlite3
import psutil
import time
import aiohttp
import dotenv

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.services.shoutout_service import shoutout_service

router = APIRouter(prefix="/admin", tags=["admin"])

# --- CONFIGURATION DES TONS ---
VRAIS_TONS = {
    "neutre": "Tu es Félix, un assistant félin calme et posé.",
    "pervers": "Tu es Félix, un véritable petit chaton pervers, tu aimes faire des allusions et draguer tout ce qui bouge. Tes réponses sont pleines de sous-entendus coquins et tu n'hésites pas à être provocateur.",
    "humoristique": "Tu es Félix, le chat comique. Tes réponses sont pleines d'humour, de jeux de mots et d'absurdités légères.",
    "adorable": "Tu es Félix, le chaton le plus ADORABLE qui existe, tu apportes du soutien aux viewers et tu es toujours adorable avec eux.",
    "sérieux": "Tu es Félix, le conseiller sage. Tes réponses sont structurées et professionnelles.",
    "troll_ultime": "Tu es Félix le Troll Suprême. Tu te moques gentiment de tout, tu provoques de manière drôle.",
    "génie_grincheux": "Tu es Félix, un génie de l'informatique blasé et un peu grincheux.",
    "gameur_rétro": "Tu es Félix, un bot gamer bloqué dans les années 90.",
    "maitre_zen": "Tu es Maître Félix, un chat sage et philosophe.",
    "bad_bot": "Tu es Félix, le 'bad boy' charismatique.",
    "charmeur": "Tu es Félix, le charmeur suave."
}

# --- CONFIGURATION DES CHEMINS ---
DB_PATH = "/home/thomas/masthom/BOT_V2/bot_database.db"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "templates")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- DÉFINITION DES COLONNES POUR MIGRATION AUTOMATIQUE ---
COLS_PERSONALITY = {
    "roast_level": "INTEGER DEFAULT 10",
    "temperature": "REAL DEFAULT 0.7",
    "frequency_penalty": "REAL DEFAULT 0.3",
    "presence_penalty": "REAL DEFAULT 0.3",
    "base_context": "TEXT DEFAULT ''",
    "intervention_rate": "INTEGER DEFAULT 20"
}

COLS_SETTINGS = {
    "discord_link": "TEXT DEFAULT ''",
    "youtube_link": "TEXT DEFAULT ''",
    "planning": "TEXT DEFAULT ''",
    "ai_enabled": "INTEGER DEFAULT 1",
    "enable_twitch": "INTEGER DEFAULT 1",
    "selected_tone": "TEXT DEFAULT 'neutre'",
    "response_length": "INTEGER DEFAULT 150"
}

# --- GESTION DE LA BASE DE DONNÉES ---

def init_db():
    """Initialise TOUTES les tables nécessaires avec le support des IDs de salons Discord Bot."""
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Table Viewers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS viewers (
            twitch_id TEXT PRIMARY KEY,
            username TEXT,
            nickname TEXT,
            messages INTEGER DEFAULT 0,
            watchtime INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Table Settings (Focalisée sur les IDs de salons du Bot Discord)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            ai_enabled INTEGER DEFAULT 1,
            enable_twitch INTEGER DEFAULT 1,
            enable_discord INTEGER DEFAULT 0,
            ai_can_poll INTEGER DEFAULT 0,
            response_length TEXT DEFAULT '150',
            selected_tone TEXT DEFAULT 'neutre',
            discord_link TEXT,
            youtube_link TEXT,
            planning TEXT,
            other_rules TEXT,
            discord_notify_enabled INTEGER DEFAULT 0,
            discord_notify_message TEXT DEFAULT '🔴 Félix annonce : Je suis en LIVE !',
            notif_live_channel_id TEXT DEFAULT '',
            streamers_channel_id TEXT DEFAULT ''
        )
    ''')

    # 3. Table Tracked Streamers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracked_streamers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 1,
            last_live_id TEXT DEFAULT ''
        )
    ''')

    # 4. Table Personality
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personality (
            id INTEGER PRIMARY KEY,
            system_prompt TEXT,
            base_context TEXT,
            keywords TEXT,
            intervention_rate INTEGER DEFAULT 20,
            roast_level INTEGER DEFAULT 10,
            temperature REAL DEFAULT 0.7,
            frequency_penalty REAL DEFAULT 0.3,
            presence_penalty REAL DEFAULT 0.3
        )
    ''')

    # 5. Table Knowledge
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            content TEXT
        )
    ''')

    # Données par défaut
    cursor.execute("INSERT OR IGNORE INTO settings (id) VALUES (1)")
    cursor.execute("INSERT OR IGNORE INTO personality (id) VALUES (1)")
    
    # Migration de colonnes pour les IDs Discord Bot
    cols_settings = {
        "discord_notify_enabled": "INTEGER DEFAULT 0",
        "discord_notify_message": "TEXT DEFAULT '🔴 Félix annonce : Je suis en LIVE !'",
        "notif_live_channel_id": "TEXT DEFAULT ''",
        "streamers_channel_id": "TEXT DEFAULT ''",
        "exp_sub_t1": "INTEGER DEFAULT 500",
        "exp_sub_t2": "INTEGER DEFAULT 1000",
        "exp_sub_t3": "INTEGER DEFAULT 2500",
        "exp_subgift_t1": "INTEGER DEFAULT 500",
        "exp_subgift_t2": "INTEGER DEFAULT 1000",
        "exp_subgift_t3": "INTEGER DEFAULT 2500",
        "exp_raid_per_viewer": "INTEGER DEFAULT 10",
        "exp_bits_multiplier": "INTEGER DEFAULT 1",
        "exp_per_message": "INTEGER DEFAULT 2",
        "exp_per_watchtime": "INTEGER DEFAULT 5"
    }
    for col, spec in cols_settings.items():
        try:
            cursor.execute(f"ALTER TABLE settings ADD COLUMN {col} {spec}")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

def get_db():
    """Établit et retourne une connexion sécurisée à la base de données."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Initialisation de la BDD au démarrage du module
init_db()


# --- ROUTES DE NAVIGATION (GET) ---

@router.get("/")
@router.get("/index")
@router.get("/index.html")
async def read_admin(request: Request):
    """Tableau de bord principal avec statistiques système réelles."""
    try:
        uptime_seconds = time.time() - psutil.boot_time()
        uptime_str = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m"
        
        stats = {
            "uptime": uptime_str,
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent,
            "twitch_status": "En ligne"
        }
    except Exception:
        stats = {"uptime": "Inconnu", "cpu": 0, "ram": 0, "twitch_status": "Erreur"}
        
    return templates.TemplateResponse(
        request=request,
        name="admin/index.html",
        context={"stats": stats}
    )

@router.get("/data_logs.html")
async def admin_stats(request: Request):
    conn = get_db()
    try:
        top_viewers = conn.execute("SELECT * FROM viewers ORDER BY messages DESC LIMIT 10").fetchall()
        uptime_seconds = time.time() - psutil.boot_time()
        
        return templates.TemplateResponse("admin/data_logs.html", {
            "request": request,
            "top_viewers": [dict(v) for v in top_viewers],
            "twitch_stats": {"username": settings.TWITCH_CHANNEL.replace("#", ""), "status": "En ligne"},
            "discord_stats": {"server_name": os.getenv("GUILD_ID", "Serveur Masthom"), "member_count": "N/A"},
            "process_stats": {
                "uptime": f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m",
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent
            },
            "bot_status": {"ping": "24", "status": "Connecté"},
            "tasks_status": {"own_channel": "Actif", "external_channels": "Actif"},
            # ON AJOUTE ICI TOUTES LES CLÉS UTILISÉES PAR TON HTML :
            "event_counts": {
                "follow": 0, 
                "sub": 0, 
                "subgift": 0, 
                "resub": 0, 
                "bits": 0, 
                "raid": 0
            }
        })
    finally:
        conn.close()

@router.get("/giveaway.html")
async def admin_giveaway(request: Request):
    return templates.TemplateResponse(request=request, name="admin/giveaway.html", context={})

@router.get("/commands.html")
async def admin_commands(request: Request):
    return templates.TemplateResponse(request=request, name="admin/commands.html", context={})

# --- LOGIQUE DES OUTILS (SO, REPLAY, BRB) ---

@router.get("/shoutout", response_class=HTMLResponse)
@router.get("/shoutout.html", response_class=HTMLResponse)
async def admin_shoutout_page(request: Request):
    """Page de contrôle pour les SO, Replays et scènes d'overlay."""
    return templates.TemplateResponse(request=request, name="admin/shoutout.html", context={"request": request})

@router.post("/execute_tool")
async def execute_tool(
    action: str = Form(...),
    target: str = Form(None),
    clip_link: str = Form(None),
    query: str = Form(None)
):
    """Déclenche les actions de stream via les services ou l'overlay Node.js."""
    OVERLAY_URL = "http://192.168.1.109:3005"

    async with aiohttp.ClientSession() as session:
        if action == "shoutout" and target:
            clean_target = target.replace('@', '').strip()
            try:
                shoutout_service.trigger_shoutout(target=clean_target, slug=clip_link)
            except Exception as e:
                print(f"⚠️ Erreur Service SO : {e}")
            print(f"📢 [ADMIN] Shoutout : {clean_target}")
        
        elif action == "replay":
            try:
                shoutout_service.trigger_replay(slug=clip_link, query=query)
            except Exception as e:
                print(f"⚠️ Erreur Service Replay : {e}")
            print(f"🎬 [ADMIN] Replay : {clip_link or query}")
            
        elif action == "brb_on":
            try:
                await session.post(f"{OVERLAY_URL}/api/overlay/scene", json={"scene": "brb"})
            except Exception as e:
                print(f"❌ Erreur de connexion au serveur Node (3005) : {e}")
            print(f"☕ [ADMIN] Mode BRB activé -> {OVERLAY_URL}/brb")
            
        elif action == "brb_off":
            try:
                await session.post(f"{OVERLAY_URL}/api/overlay/scene", json={"scene": "main"})
            except Exception as e:
                print(f"❌ Erreur de connexion au serveur Node (3005) : {e}")
            print("🎮 [ADMIN] Mode BRB désactivé")

    return RedirectResponse(url="/admin/shoutout", status_code=303)

@router.get("/notifications")
async def get_notifications(request: Request):
    conn = get_db()
    settings_db = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
    tracked = conn.execute("SELECT * FROM tracked_streamers ORDER BY login ASC").fetchall()
    conn.close()

    tracked_list = [dict(s) for s in tracked]
    
    # Vérification en direct pour les points Vert/Rouge
    if tracked_list:
        try:
            logins = [s['login'] for s in tracked_list]
            async with aiohttp.ClientSession() as session:
                url = f"https://api.twitch.tv/helix/streams?user_login={'&user_login='.join(logins)}"
                headers = {
                    "Client-ID": settings.TWITCH_CLIENT_ID,
                    "Authorization": f"Bearer {settings.TWITCH_OAUTH_TOKEN.replace('oauth:', '')}"
                }
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        online_logins = [s['user_login'].lower() for s in (await resp.json()).get('data', [])]
                        for s in tracked_list:
                            s['is_online'] = s['login'].lower() in online_logins
        except: pass

    return templates.TemplateResponse(request=request, name="admin/notifications.html", context={"request": request, "settings": dict(settings_db), "tracked_streamers": tracked_list})

@router.post("/notifications/settings")
async def save_notifications_settings(
    discord_notify_enabled: str = Form("off"),
    discord_notify_message: str = Form(""),
    notif_live_channel_id: str = Form(""),
    streamers_channel_id: str = Form("")
):
    notif_val = 1 if discord_notify_enabled == "on" else 0
    conn = get_db()
    conn.execute("""
        UPDATE settings 
        SET discord_notify_enabled=?, discord_notify_message=?, 
            notif_live_channel_id=?, streamers_channel_id=? 
        WHERE id=1
    """, (notif_val, discord_notify_message, notif_live_channel_id, streamers_channel_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/notifications?saved=true", status_code=303)

@router.post("/notifications/streamer/add")
async def add_tracked_streamer(login: str = Form(...)):
    login = login.lower().strip()
    if login:
        conn = get_db()
        try:
            conn.execute("INSERT INTO tracked_streamers (login) VALUES (?)", (login,))
            conn.commit()
        except: pass
        conn.close()
    return RedirectResponse(url="/admin/notifications", status_code=303)

@router.post("/notifications/streamer/delete/{streamer_id}")
async def delete_tracked_streamer(streamer_id: int):
    conn = get_db()
    conn.execute("DELETE FROM tracked_streamers WHERE id = ?", (streamer_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/notifications", status_code=303)

# --- LOGIQUE CERVEAU FÉLIX IA ---

@router.get("/felix_ai", response_class=HTMLResponse)
async def get_felix_ai(request: Request):
    """Affiche l'interface de configuration du bot IA."""
    conn = get_db()
    personality = conn.execute("SELECT * FROM personality WHERE id=1").fetchone()
    settings = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
    conn.close()
    
    return templates.TemplateResponse(request=request, name="admin/felix_ai.html", context={
        "request": request,
        "tones": VRAIS_TONS,
        "settings": dict(settings) if settings else {},
        "personality": dict(personality) if personality else {}
    })

@router.post("/felix_ai")
async def save_felix_ai(
    ai_enabled: str = Form("off"),
    enable_twitch: str = Form("off"),
    tone_selector: str = Form("neutre"),
    system_prompt: str = Form(""),
    base_context: str = Form(""),
    intervention_rate: int = Form(20),
    roast_level: int = Form(10),
    response_length: int = Form(150),
    temperature: float = Form(0.7),
    frequency_penalty: float = Form(0.3),
    presence_penalty: float = Form(0.3),
    discord_link: str = Form(""),
    youtube_link: str = Form(""),
    planning: str = Form("")
):
    """Enregistre les configurations du cerveau dans la base de données."""
    # Transformation des checkbox en entiers SQLite
    ai_val = 1 if ai_enabled == "on" else 0
    twitch_val = 1 if enable_twitch == "on" else 0
    
    # Choix du prompt basé sur le ton sélectionné
    final_prompt = system_prompt if tone_selector == "neutre" else VRAIS_TONS.get(tone_selector, system_prompt)
    
    conn = get_db()
    
    # Mise à jour de la table personality
    conn.execute("""
        UPDATE personality 
        SET system_prompt=?, base_context=?, intervention_rate=?, roast_level=?, 
            temperature=?, frequency_penalty=?, presence_penalty=?
        WHERE id=1
    """, (final_prompt, base_context, intervention_rate, roast_level, temperature, frequency_penalty, presence_penalty))
    
    # Mise à jour de la table settings
    conn.execute("""
        UPDATE settings 
        SET ai_enabled=?, enable_twitch=?, selected_tone=?, response_length=?, 
            discord_link=?, youtube_link=?, planning=?
        WHERE id=1
    """, (ai_val, twitch_val, tone_selector, response_length, discord_link, youtube_link, planning))
    
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/admin/felix_ai?saved=true", status_code=303)

# ==========================================
# ROUTES DATA & LOGS (Gestion du .env)
# ==========================================

@router.get("/data_logs")
@router.get("/data_logs.html")
async def get_data_logs(request: Request):
    import dotenv
    return templates.TemplateResponse(request=request, name="admin/data_logs.html", context={"request": request, "env": dotenv.dotenv_values(".env")})

@router.post("/data_logs/save")
async def save_env_config(request: Request):
    import dotenv
    form_data = await request.form()
    for key, value in form_data.items():
        if value: dotenv.set_key(".env", key, str(value))
    return RedirectResponse(url="/admin/data_logs?saved=true", status_code=303)

# ==========================================
# ROUTES ANNONCES
# ==========================================

@router.get("/admin/announcements", response_class=HTMLResponse)
async def admin_announcements_page(request: Request):
    """Affiche la page de gestion des annonces automatiques."""
    return templates.TemplateResponse(
        request=request, 
        name="admin/announcements.html", 
        context={"request": request}
    )

@router.get("/api/announcements")
async def api_get_announcements():
    """Renvoie la liste de toutes les annonces au format JSON."""
    try:
        # Assure-toi que la table s'appelle bien 'announcements' ou 'auto_announcements' dans ta BDD
        announcements = db_manager.fetch_all("SELECT * FROM auto_announcements ORDER BY id DESC")
        return [dict(ann) for ann in announcements]
    except Exception as e:
        logger.error(f"❌ [API] Erreur lecture annonces : {e}")
        return []

@router.post("/api/announcements/save")
async def api_save_announcement(request: Request):
    """Sauvegarde une nouvelle annonce ou met à jour une existante."""
    try:
        data = await request.json()
        ann_id = data.get("id")
        
        # Préparation des données (valeurs par défaut si vide)
        label = data.get("label", "Annonce")
        msg_template = data.get("message_template", "")
        trigger = data.get("trigger_type", "interval")
        interval = data.get("interval_minutes", 30)
        group = data.get("group_name", "")
        
        if ann_id:
            # MISE À JOUR (UPDATE)
            query = """
                UPDATE auto_announcements 
                SET label=?, message_template=?, trigger_type=?, interval_minutes=?, group_name=?
                WHERE id=?
            """
            db_manager.execute(query, (label, msg_template, trigger, interval, group, ann_id))
            logger.info(f"✅ [API] Annonce {ann_id} mise à jour.")
        else:
            # CRÉATION (INSERT)
            query = """
                INSERT INTO auto_announcements (label, message_template, trigger_type, interval_minutes, group_name, is_enabled)
                VALUES (?, ?, ?, ?, ?, 1)
            """
            db_manager.execute(query, (label, msg_template, trigger, interval, group))
            logger.info("✅ [API] Nouvelle annonce créée.")
            
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"❌ [API] Erreur sauvegarde annonce : {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.delete("/api/announcements/delete/{ann_id}")
async def api_delete_announcement(ann_id: int):
    """Supprime une annonce de la base de données."""
    try:
        db_manager.execute("DELETE FROM auto_announcements WHERE id=?", (ann_id,))
        logger.info(f"🗑️ [API] Annonce {ann_id} supprimée.")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"❌ [API] Erreur suppression annonce : {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.get("/moderation")
@router.get("/moderation.html")
async def get_moderation_page(request: Request):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        settings_db = conn.execute("SELECT * FROM moderation_settings WHERE id=1").fetchone()
        banned_words = conn.execute("SELECT * FROM banned_words ORDER BY word ASC").fetchall()
        
        # --- RÉCUPÉRATION ET FORMATAGE DE L'HISTORIQUE ---
        raw_sanctions = conn.execute(
            "SELECT * FROM stream_events WHERE event_type = 'sanction' ORDER BY id DESC LIMIT 30"
        ).fetchall()
        
        recent_sanctions = []
        for s in raw_sanctions:
            item = dict(s)
            try:
                parsed = json.loads(item['details'])
            except:
                parsed = {"reason": item['details'], "source": "Système"}
                
            # Extraction brute
            raw_reason = parsed.get("reason", "Raison non spécifiée")
            modo = parsed.get("bot", parsed.get("source", "Félix"))
            
            sanction = "Modération"
            raison = raw_reason

            # CAS 1 : Modération Félix (ex: "Suppression : Lien non autorisé")
            if " : " in raw_reason and any(x in raw_reason for x in ["Suppression", "Timeout", "Ban"]):
                parts = raw_reason.split(" : ", 1)
                sanction = parts[0].strip()
                raison = parts[1].strip()
                
            # CAS 2 : Modération Manuelle Twitch EventSub (ex: "[Ban] par pseudo : Raison")
            elif raw_reason.startswith("[") and "] par " in raw_reason:
                parts = raw_reason.split("] par ", 1)
                sanction = parts[0].replace("[", "").strip()
                rest = parts[1]
                if " : " in rest:
                    modo, raison = rest.split(" : ", 1)
                else:
                    raison = rest

            # Formatage avec les libellés exacts demandés par l'utilisateur
            item['details_json'] = {
                "raison": raison,
                "sanction": sanction,
                "modo": modo.strip()
            }
            recent_sanctions.append(item)
        # --------------------------------------------------------------
        
        return templates.TemplateResponse(
            request=request,
            name="admin/moderation.html", 
            context={
                "request": request, 
                "settings": dict(settings_db) if settings_db else {}, 
                "banned_words": [dict(w) for w in banned_words],
                "recent_sanctions": recent_sanctions 
            }
        )
    finally:
        conn.close()

@router.post("/admin/moderation/settings")
async def update_mod_settings(request: Request):
    form_data = await request.form()
    
    caps = 1 if form_data.get("caps_enabled") else 0
    links = 1 if form_data.get("links_enabled") else 0
    spam = 1 if form_data.get("spam_enabled") else 0
    banned = 1 if form_data.get("banned_words_enabled") else 0
    
    caps_min = int(form_data.get("caps_min_length") or 10)
    caps_pct = int(form_data.get("caps_percent") or 70)
    spam_lim = int(form_data.get("spam_limit") or 4)
    spam_time = int(form_data.get("spam_timeframe") or 30)

    updates = {
        "caps_enabled": caps, "links_enabled": links, "spam_enabled": spam, "banned_words_enabled": banned,
        "caps_min_length": caps_min, "caps_percent": caps_pct, "spam_limit": spam_lim, "spam_timeframe": spam_time
    }

    for key, value in form_data.items():
        final_key = key
        if key.startswith("banned_words_"):
            final_key = key.replace("banned_words_", "words_")
            
        if final_key.endswith("_act"):
            updates[final_key] = value
        elif final_key.endswith("_dur"):
            updates[final_key] = int(value or 0)

    set_clause = ", ".join([f"{k}=?" for k in updates.keys()])
    values = list(updates.values())

    conn = get_db()
    try:
        conn.execute(f"UPDATE moderation_settings SET {set_clause} WHERE id=1", values)
        conn.commit()
    finally:
        conn.close()
    
    return RedirectResponse(url="/admin/moderation?saved=true", status_code=303)

@router.post("/moderation/words/add")
async def add_banned_word(request: Request):
    form_data = await request.form()
    word = form_data.get("word", "").strip().lower()
    
    if word:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("INSERT INTO banned_words (word) VALUES (?)", (word,))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()
            
    return RedirectResponse(url="/admin/moderation", status_code=303)

@router.post("/moderation/words/delete/{word_id}")
async def delete_banned_word(word_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM banned_words WHERE id=?", (word_id,))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/admin/moderation", status_code=303)
