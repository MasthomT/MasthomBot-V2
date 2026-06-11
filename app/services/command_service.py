import logging
import time
import json
import asyncio
import random
import aiohttp
from datetime import datetime, timezone
from app.core.database import get_db_connection
from app.core.config import settings

logger = logging.getLogger("masthbot.commands")

_cooldown_global: dict = {}
_cooldown_user: dict   = {}

# ─── Rôles ────────────────────────────────────────────────────────────────────

def _check_role(user_role: str, min_role: str) -> bool:
    hierarchy = ["viewer", "sub", "vip", "mod", "admin"]
    try:
        return hierarchy.index(user_role) >= hierarchy.index(min_role)
    except ValueError:
        return False

def _get_user_role(is_mod, is_sub, is_vip, is_admin) -> str:
    if is_admin: return "admin"
    if is_mod:   return "mod"
    if is_vip:   return "vip"
    if is_sub:   return "sub"
    return "viewer"

# ─── Planification horaire ────────────────────────────────────────────────────

def _is_in_schedule(active_from, active_until) -> bool:
    """Retourne True si l'heure actuelle est dans la plage autorisée."""
    if not active_from or not active_until:
        return True  # Pas de restriction
    now = datetime.now().time()
    # Gère le cas overnight (ex: 22:00 → 02:00)
    if active_from <= active_until:
        return active_from <= now <= active_until
    else:
        return now >= active_from or now <= active_until

# ─── Résolution des variables ─────────────────────────────────────────────────

async def _resolve_variables(text: str, username: str, viewer_data: dict, stream_data: dict, user_input: str = "") -> str:
    """Remplace toutes les variables {xxx} dans le texte."""
    if not text:
        return text

    now = datetime.now()
    JOURS  = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    MOIS   = ["Janvier","Février","Mars","Avril","Mai","Juin",
               "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

    # Remplacement de l'input utilisateur (!commande <texte>)
    text = text.replace("{input}", user_input)
    text = text.replace("{target}", user_input.replace("@", "") if user_input else username)

    # Viewer
    text = text.replace("{username}",    username)
    text = text.replace("{display_name}", viewer_data.get("display_name") or username)
    text = text.replace("{level}",       str(viewer_data.get("level", 1)))
    text = text.replace("{points}",      str(viewer_data.get("points", 0)))
    text = text.replace("{messages}",    str(viewer_data.get("messages", 0)))
    text = text.replace("{rank}",        str(viewer_data.get("rank", "?")))
    text = text.replace("{pronoms}",     viewer_data.get("pronouns") or "")
    text = text.replace("{is_sub}",      "oui" if viewer_data.get("is_sub") else "non")
    text = text.replace("{is_vip}",      "oui" if viewer_data.get("is_vip") else "non")
    text = text.replace("{is_mod}",      "oui" if viewer_data.get("is_mod") else "non")
    text = text.replace("{follow_date}", str(viewer_data.get("follow_date", "?")))
    text = text.replace("{sub_months}",  str(viewer_data.get("sub_months", 0)))
    text = text.replace("{badges}",      viewer_data.get("badges") or "")

    # Watchtime formaté
    wt = viewer_data.get("watchtime", 0) or 0
    h, m = divmod(wt // 60, 60)
    text = text.replace("{watchtime}", f"{h}h{m:02d}")

    # Stream
    text = text.replace("{stream_title}",   stream_data.get("title", ""))
    text = text.replace("{game}",           stream_data.get("game", ""))
    text = text.replace("{viewer_count}",   str(stream_data.get("viewer_count", 0)))
    text = text.replace("{stream_duration}", stream_data.get("duration", ""))
    text = text.replace("{uptime}",         stream_data.get("uptime", ""))
    text = text.replace("{channel}",        stream_data.get("channel", ""))
    text = text.replace("{last_clip}",      stream_data.get("last_clip", ""))
    text = text.replace("{last_sub}",       stream_data.get("last_sub", ""))
    text = text.replace("{last_follow}",    stream_data.get("last_follow", ""))

    # Date / Heure
    text = text.replace("{date}",      now.strftime("%d/%m/%Y"))
    text = text.replace("{time}",      now.strftime("%H:%M"))
    text = text.replace("{day}",       JOURS[now.weekday()])
    text = text.replace("{month}",     MOIS[now.month - 1])
    text = text.replace("{year}",      str(now.year))
    text = text.replace("{timestamp}", str(int(now.timestamp())))

    # Bot / Config
    text = text.replace("{discord}",  stream_data.get("discord_link", ""))
    text = text.replace("{youtube}",  stream_data.get("youtube_link", ""))
    text = text.replace("{planning}", stream_data.get("planning", ""))
    text = text.replace("{bot_name}", "Félix")

    # Aléatoire
    if "{random_viewer}" in text:
        rnd = await _get_random_viewer(username)
        text = text.replace("{random_viewer}", rnd)

    # {number:min:max}
    import re
    for match in re.findall(r"\{number:(\d+):(\d+)\}", text):
        lo, hi = int(match[0]), int(match[1])
        text = re.sub(r"\{number:\d+:\d+\}", str(random.randint(lo, hi)), text, count=1)

    return text

async def handle_custom_command(
    command_name: str,
    username: str,
    viewer_data: dict = None,
    user_input: str = "", # Nouvel argument !
    is_mod: bool = False,
    is_sub: bool = False,
    is_vip: bool = False,
    is_admin: bool = False,
) -> dict | None:
    now  = time.time()
    name = command_name.lower().strip()

    async with get_db_connection() as conn:
        # On cherche si le mot tapé correspond au nom principal OU à un des alias
        c = await conn.execute(
            "SELECT * FROM custom_commands WHERE (name = $1 OR $1 = ANY(string_to_array(replace(aliases, ' ', ''), ','))) AND is_active = TRUE",
            (name,)
        )
        row = await c.fetchone()

    if not row:
        return None

    cmd = dict(row)

    # Planification horaire
    if not _is_in_schedule(cmd.get("active_from"), cmd.get("active_until")):
        logger.debug(f"⏰ !{name} hors plage horaire")
        return None

    # Droits
    user_role = _get_user_role(is_mod, is_sub, is_vip, is_admin)
    if not _check_role(user_role, cmd["min_role"]):
        return None

    # Cooldown global et user...
    if name in _cooldown_global and (now - _cooldown_global[name]) < cmd["cooldown_global"]:
        return None
    user_key = f"{name}:{username.lower()}"
    if user_key in _cooldown_user and (now - _cooldown_user[user_key]) < cmd["cooldown_user"]:
        return None

    _cooldown_global[name]    = now
    _cooldown_user[user_key]  = now

    async with get_db_connection() as conn:
        await conn.execute("UPDATE custom_commands SET use_count = use_count + 1, updated_at = NOW() WHERE name = $1", (name,))

    vd = viewer_data or {}
    sd = await _get_stream_data()
    vd.update({"is_mod": is_mod, "is_sub": is_sub, "is_vip": is_vip})

    # Lecture de la commande composite (JSON)
    try:
        payload = json.loads(cmd["response"])
    except:
        # Rétrocompatibilité avec les anciennes commandes
        payload = {"text": cmd["response"]} if cmd["type"] == "text" else {cmd["type"]: cmd["response"]}
        if cmd.get("chat_response"):
            payload["text"] = cmd["chat_response"]

    # --- CALCUL DE L'ÂGE DE FOLLOW ---
    follow_date_raw = vd.get("follow_date")
    
    # Valeurs par défaut propres si la personne n'est pas follow
    follow_date_formatted = "jamais"
    follow_years = "0"
    follow_months = "0"
    follow_days = "0"

    # 🌐 NOUVEAUTÉ : On interroge l'API publique IVR
    if not follow_date_raw:
        try:
            # 👉 CORRECTION ICI : D'abord le viewer ({username}), ENSUITE ta chaîne (masthom_)
            url = f"https://api.ivr.fi/v2/twitch/subage/{username}/masthom_"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Si le viewer follow, l'API renvoie la date dans "followedAt"
                        if data and data.get("followedAt"):
                            follow_date_raw = data["followedAt"]
                            logger.info(f"🌐 [DEBUG MYINFO] Date récupérée via IVR API pour {username}.")
                        # PAS DE ELSE/WARNING ICI POUR NE PAS POLLUER LES LOGS
        except Exception:
            # On ignore l'erreur silencieusement si l'API est injoignable
            pass

    # 🧮 LE CALCUL (Si on a fini par trouver une date)
    if follow_date_raw:
        try:
            clean_date = str(follow_date_raw).replace('Z', '+00:00')
            if '+' not in clean_date and '-' not in clean_date[10:]:
                 clean_date += '+00:00'

            fd = datetime.fromisoformat(clean_date)
            now = datetime.now(timezone.utc)

            follow_date_formatted = fd.strftime("%d/%m/%Y")

            diff = now - fd
            total_days = diff.days

            follow_years = str(total_days // 365)
            follow_months = str((total_days % 365) // 30)
            follow_days = str((total_days % 365) % 30)
            logger.info(f"✅ [DEBUG MYINFO] Calcul réussi pour {username} : {follow_years} ans, {follow_months} mois.")
        except Exception as e:
            logger.error(f"❌ [DEBUG MYINFO] Erreur de calcul pour {username} : {e}")
            follow_date_formatted = "?"
    else:
        # Utilisation de logger.warning pour signaler l'absence de donnée
        # logger.warning(f"⚠️ [DEBUG MYINFO] Aucune date de follow (None) trouvée pour {username}.")
        pass # Le mot clé 'pass' permet de garder le bloc vide sans faire planter Python

    # ==========================================
    # 1. TEXTE (Chat)
    # ==========================================
    chat_text = payload.get("text", "")
    if chat_text:
        # 🎲 NOUVEAUTÉ : Tirage au sort si plusieurs phrases sont séparées par ||
        if "||" in chat_text:
            phrases = [p.strip() for p in chat_text.split("||") if p.strip()]
            if phrases:
                chat_text = random.choice(phrases)

        # 🛡️ SÉCURITÉ : On s'assure que les variables sont en texte (Anti-Crash pour le Streamer)
        fd_str = str(follow_date_formatted) if follow_date_formatted else "Inconnue"
        fy_str = str(follow_years) if follow_years else "0"
        fm_str = str(follow_months) if follow_months else "0"
        fd_days = str(follow_days) if follow_days else "0"

        # Remplacement sécurisé
        chat_text = chat_text.replace("{follow_date}", fd_str)
        chat_text = chat_text.replace("{follow_years}", fy_str)
        chat_text = chat_text.replace("{follow_months}", fm_str)
        chat_text = chat_text.replace("{follow_days}", fd_days)
        
        # Et on résout le reste des variables ({username}, etc.)
        chat_text = await _resolve_variables(chat_text, username, vd, sd, user_input)
        
        # 🕵️‍♂️ Petit log de debug pour vérifier que le texte est bien généré
        #logger.info(f"💬 Message texte généré : {chat_text}")

    # ==========================================
    # 2. IMAGE
    # ==========================================
    img_file = payload.get("image", "")
    if img_file:
        await _trigger_overlay("image", {"filename": img_file, "username": username})

    # ==========================================
    # 3. SON
    # ==========================================
    snd_file = payload.get("sound", "")
    if snd_file:
        await _trigger_overlay("sound", {"filename": snd_file, "username": username})

    # ==========================================
    # 4. OBS (Multi-Actions Séquentielles)
    # ==========================================
    # On récupère la liste des actions OBS (s'il n'y en a qu'une ancienne, on la convertit en liste)
    obs_payload = payload.get("obs", [])
    if isinstance(obs_payload, dict) and obs_payload.get("action"):
        obs_actions = [obs_payload]
    else:
        obs_actions = obs_payload if isinstance(obs_payload, list) else []

    if obs_actions:
        # On crée une fonction asynchrone interne pour ne pas bloquer le bot pendant les délais
        async def execute_obs_sequence():
            for obs_data in obs_actions:
                # 1. Gestion du délai avant l'action
                delay_ms = float(obs_data.get("delay", 0))
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000.0)
                
                # 2. Préparation des variables
                obs_data["username"] = username
                if obs_data.get("text"):
                    obs_text = obs_data["text"]
                    obs_text = obs_text.replace("{follow_date}", follow_date_formatted)
                    obs_text = obs_text.replace("{follow_years}", follow_years)
                    obs_text = obs_text.replace("{follow_months}", follow_months)
                    obs_text = obs_text.replace("{follow_days}", follow_days)
                    obs_data["text"] = await _resolve_variables(obs_text, username, vd, sd, user_input)

                # 3. Exécution
                try:
                    await _trigger_overlay("obs_command", obs_data)
                except Exception as e:
                    logger.error(f"❌ Erreur action OBS pour !{name}: {e}")

        # Lancement de la séquence en arrière-plan
        asyncio.create_task(execute_obs_sequence())

    # Retourne le texte à envoyer dans le chat (s'il y en a un)
    return {"type": "multi", "content": chat_text if chat_text else None}


async def _get_random_viewer(exclude: str) -> str:
    """Retourne un pseudo aléatoire parmi les viewers récents."""
    try:
        async with get_db_connection() as conn:
            c = await conn.execute(
                "SELECT username FROM viewers WHERE LOWER(username) != $1 ORDER BY last_seen DESC LIMIT 20",
                (exclude.lower(),)
            )
            rows = await c.fetchall()
        if rows:
            return random.choice(rows)[0]
    except Exception:
        pass
    return "quelqu'un"


async def _get_stream_data() -> dict:
    """Récupère les données du stream depuis la DB settings."""
    try:
        async with get_db_connection() as conn:
            c = await conn.execute("SELECT * FROM personality LIMIT 1")
            row = await c.fetchone()
            if row:
                d = dict(row)
                return {
                    "discord_link": d.get("discord_link", ""),
                    "youtube_link": d.get("youtube_link", ""),
                    "planning":     d.get("planning", ""),
                }
    except Exception:
        pass
    return {}


# ─── Overlay trigger ──────────────────────────────────────────────────────────

async def _trigger_overlay(event_type: str, details: dict):
    # 1. On affiche ce qu'on essaie d'envoyer pour faciliter la compréhension
    logger.info(f"Tentative d'envoi à l'overlay : Type={event_type}, Détails={details}")
    
    try:
        async with aiohttp.ClientSession() as session:
            # 2. On envoie la requête à l'URL définie dans les réglages
            response = await session.post(
                f"{settings.OVERLAY_NODE_URL}/api/trigger",
                json={"type": event_type, "details": details},
                timeout=aiohttp.ClientTimeout(total=2)
            )
            
            # 3. On vérifie le code de statut de la réponse HTTP
            if response.status == 200:
                logger.info("✅ Requête envoyée avec succès à l'overlay !")
            else:
                logger.error(f"❌ L'overlay a répondu avec une erreur : {response.status}")
                
    except Exception as e:
        # 4. En cas d'échec de la connexion, on affiche l'erreur exacte
        logger.warning(f"⚠️ Overlay non joignable ({event_type}) : {e}")


# ─── CRUD (utilisé par admin_commands.py) ────────────────────────────────────

async def list_commands(active_only: bool = False) -> list:
    async with get_db_connection() as conn:
        q = "SELECT * FROM custom_commands"
        if active_only:
            q += " WHERE is_active = TRUE"
        q += " ORDER BY name ASC"
        c    = await conn.execute(q)
        rows = await c.fetchall()
        return [dict(r) for r in rows]


async def delete_command(cmd_id: int) -> bool:
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM custom_commands WHERE id = $1", (cmd_id,))
        return True
