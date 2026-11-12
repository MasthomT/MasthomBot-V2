"""
app/services/bot_system_commands_service.py

Gestion des commandes système du bot (so, level, etc.).
- Stocke nom, activation, rôle min, messages dans la DB
- Cache en mémoire avec TTL 60s (invalidé manuellement à la sauvegarde admin)
- Fournit le helper msg(key, field, **vars) pour interpoler les messages
"""

import json
import re
import time
import logging
from typing import Optional

logger = logging.getLogger("masthbot.syscmds")

# ── Définition de toutes les commandes système ──────────────────────────────
# command_key  : identifiant interne immuable (= nom du décorateur twitchio)
# label        : nom affiché dans l'admin
# description  : à quoi ça sert
# default_name : déclencheur par défaut (!so, !level, …)
# default_role : qui peut l'utiliser ('everyone','sub','vip','mod','broadcaster')
# tags         : variables disponibles dans les messages, affichées dans l'UI
# messages     : dict {champ: message_par_défaut}

SYSTEM_COMMANDS_DEFINITION = [
    {
        "command_key": "so",
        "label": "Shoutout",
        "description": "Met en avant un streamer dans le chat + overlay",
        "default_name": "so",
        "default_role": "mod",
        "tags": {
            "success":       ["{target}", "{game}", "{url}"],
            "success_basic": ["{target}", "{url}"],
            "error_url":     [],
            "usage":         ["{command}"],
        },
        "messages": {
            "success":       "🎬 Allez donner de la force à @{target} qui jouait récemment à {game} ! {url} 💜",
            "success_basic": "Foncez voir @{target} ! {url}",
            "error_url":     "❌ Impossible de récupérer le pseudo depuis ce lien ! Vérifie ton URL.",
            "usage":         "Miaou ! Pseudo ou lien requis : !{command} pseudo",
        },
    },
    {
        "command_key": "play",
        "label": "Lecteur (clip, TikTok, YouTube, Instagram)",
        "description": (
            "Affiche sur l'overlay ce qu'on lui donne : !play (seul) = le dernier clip de la chaîne · "
            "!play <mots du titre d'un de tes clips> · !play <lien de clip Twitch> · !play <lien TikTok> · "
            "!play <lien YouTube> · !play <lien Instagram> · !play tiktok (dernier TikTok). "
            "Vidéos limitées à 5 minutes."
        ),
        "default_name": "play",
        "default_aliases": ["lecteur"],
        "default_role": "mod",
        "tags": {
            "clip_playing":          ["{title}", "{url}", "{broadcaster}"],
            "clip_not_found":        [],
            "tiktok_success":        ["{title}", "{url}"],
            "tiktok_none":           [],
            "tiktok_download_error": [],
            "tiktok_wrong_account":  ["{broadcaster}", "{tiktok_account}"],
            "video_success":         ["{title}", "{url}"],
            "video_download_error":  [],
            "video_too_long":        ["{duration}", "{max}"],
        },
        "messages": {
            "clip_playing":          "🎬 Replay : {title} — twitch.tv/{broadcaster} ({url})",
            "clip_not_found":        "❌ Aucun clip trouvé.",
            "tiktok_success":        "🎵 TikTok affiché à l'écran ! — {title} {url}",
            "tiktok_none":           "❌ Aucune vidéo TikTok connue pour le moment.",
            "tiktok_download_error": "❌ Impossible de récupérer cette vidéo TikTok. Vérifie le lien !",
            "tiktok_wrong_account":  "❌ Via la récompense, seuls les TikTok de @{tiktok_account} peuvent être affichés.",
            "video_success":         "🎬 Vidéo affichée à l'écran ! — {title} {url}",
            "video_download_error":  "❌ Impossible de récupérer cette vidéo. Vérifie le lien (YouTube / Instagram) !",
            "video_too_long":        "❌ Vidéo trop longue ({duration}) : {max} maximum.",
        },
    },
    {
        "command_key": "renotif",
        "label": "Renvoyer notif Discord",
        "description": "Renvoie la notification de live sur Discord",
        "default_name": "renotif",
        "default_role": "mod",
        "tags": {
            "success":    ["{game}"],
            "no_live":    [],
            "no_channel": [],
        },
        "messages": {
            "success":    "✅ Notification renvoyée sur Discord avec la catégorie : {game} !",
            "no_live":    "⏳ Twitch ne te voit pas en live. Attends 1 minute et réessaie !",
            "no_channel": "❌ Aucun salon Discord n'est configuré.",
        },
    },
    {
        "command_key": "checkcopains",
        "label": "Check copains en live",
        "description": "Force l'envoi des notifications Discord pour les copains en live",
        "default_name": "checkcopains",
        "default_role": "mod",
        "tags": {
            "scanning":    ["{count}"],
            "done":        ["{count}"],
            "empty":       [],
            "no_channel":  [],
            "no_partners": [],
        },
        "messages": {
            "scanning":    "🔍 Scan des {count} copains...",
            "done":        "✅ {count} alertes envoyées !",
            "empty":       "💤 Aucun copain n'est en ligne.",
            "no_channel":  "❌ Aucun salon Discord configuré.",
            "no_partners": "⚠️ Aucun partenaire surveillé.",
        },
    },
    {
        "command_key": "testpoll",
        "label": "Test sondage overlay",
        "description": "Envoie un faux sondage de test à l'overlay",
        "default_name": "testpoll",
        "default_role": "mod",
        "tags": {
            "success": [],
        },
        "messages": {
            "success": "🛠️ Faux sondage de test envoyé à l'overlay !",
        },
    },
    {
        "command_key": "level",
        "label": "Niveau EXP",
        "description": "Affiche le niveau et l'EXP du viewer",
        "default_name": "level",
        "default_role": "everyone",
        "tags": {
            "level": ["{user}", "{level}", "{points}", "{next_xp}"],
            "new":   ["{user}"],
        },
        "messages": {
            "level": "@{user}, tu es Niveau {level} avec {points} EXP ! (Prochain niveau à {next_xp} EXP) 🌟",
            "new":   "@{user}, tu es Niveau 1 avec 0 EXP ! Parle dans le chat pour progresser. 🐾",
        },
    },
    {
        "command_key": "rang",
        "label": "Classement EXP",
        "description": "Affiche le rang du viewer dans le classement EXP",
        "default_name": "rang",
        "default_role": "everyone",
        "tags": {
            "rank":       ["{user}", "{rank}", "{leaderboard}"],
            "empty":      ["{user}"],
            "not_ranked": ["{user}"],
        },
        "messages": {
            "rank":       "🏆 Classement (Rang #{rank}) : {leaderboard}",
            "empty":      "@{user}, le classement est vide pour le moment !",
            "not_ranked": "@{user}, tu n'as pas encore d'EXP pour être classé ! 🐾",
        },
    },
    {
        "command_key": "screamer",
        "label": "Screamer",
        "description": "Déclenche un screamer plein écran dans OBS (réglages : /admin/alerts ; il doit y être activé)",
        "default_name": "screamer",
        "default_role": "mod",
        "tags": {
            "fired":    ["{user}"],
            "disabled": [],
        },
        "messages": {
            "fired":    "😱 Attention… {user} a lâché le SCREAMER !",
            "disabled": "😴 Le screamer est désactivé (à activer dans /admin/alerts).",
        },
    },
    {
        "command_key": "timer",
        "label": "Timer OBS",
        "description": "Lance ou arrête un timer sur l'overlay",
        "default_name": "timer",
        "default_role": "mod",
        "tags": {
            "start":   ["{minutes}", "{label}"],
            "stop":    [],
            "usage":   ["{command}"],
            "invalid": ["{command}"],
        },
        "messages": {
            "start":   "⏱️ Timer de {minutes} minute(s) lancé à l'écran : {label}",
            "stop":    "🛑 Timer effacé de l'écran !",
            "usage":   "⏱️ Usage : !{command} <minutes> [Label] (ex: !{command} 5 Pause café)",
            "invalid": "❌ La durée doit être un chiffre exact en minutes (ex: !{command} 5)",
        },
    },
    {
        "command_key": "chrono",
        "label": "Chrono OBS",
        "description": "Lance ou arrête un chronomètre sur l'overlay",
        "default_name": "chrono",
        "default_role": "mod",
        "tags": {
            "start": ["{label}"],
            "stop":  [],
        },
        "messages": {
            "start": "⏱️ Chronomètre lancé à l'écran : {label}",
            "stop":  "🛑 Chrono effacé de l'écran !",
        },
    },
    {
        "command_key": "voteclips",
        "label": "Vote clips",
        "description": "Lance un sondage pour voter pour le meilleur clip",
        "default_name": "voteclips",
        "default_role": "mod",
        "tags": {
            "success": [],
            "error":   ["{error}"],
            "denied":  [],
        },
        "messages": {
            "success": "📊 Le sondage est lancé ! Votez pour votre clip préféré en haut du t'chat !",
            "error":   "❌ Erreur : {error}",
            "denied":  "Désolé, seuls les modérateurs peuvent lancer le vote des clips !",
        },
    },
    {
        "command_key": "addvip",
        "label": "Ajouter VIP",
        "description": "Donne le statut VIP à un viewer",
        "default_name": "addvip",
        "default_role": "mod",
        "tags": {
            "success_permanent": ["{target}"],
            "success_temp":      ["{target}", "{days}"],
            "usage":             ["{command}"],
            "not_found":         ["{target}"],
        },
        "messages": {
            "success_permanent": "⭐ Consécration ! @{target} est désormais VIP à vie !",
            "success_temp":      "💎 L'élite s'agrandit ! @{target} est désormais VIP pour {days} jours !",
            "usage":             "❌ Usage: !{command} <pseudo> <jours> (Ex: !{command} Masthom_ 7) — 0 = permanent.",
            "not_found":         "❌ Le viewer @{target} n'existe pas en base de données. Il doit parler au moins une fois.",
        },
    },
    {
        "command_key": "vip",
        "label": "Statut VIP",
        "description": "Affiche le statut VIP du viewer",
        "default_name": "vip",
        "default_role": "everyone",
        "tags": {
            "not_vip":   ["{user}"],
            "permanent": ["{user}"],
            "temp":      ["{user}", "{time}", "{date}"],
            "expired":   ["{user}", "{date}"],
        },
        "messages": {
            "not_vip":   "@{user}, tu n'es pas VIP ! 😿",
            "permanent": "⭐ @{user}, ton grade VIP est Permanent ! Merci pour ton soutien éternel 💜",
            "temp":      "💎 @{user}, il te reste {time} de VIP ! (Expire le {date})",
            "expired":   "🥀 @{user}, ton grade VIP a expiré le {date}.",
        },
    },
    {
        "command_key": "permit",
        "label": "Autoriser lien",
        "description": "Autorise un viewer à poster un lien pendant 60s",
        "default_name": "permit",
        "default_role": "mod",
        "tags": {
            "success": ["{target}"],
            "usage":   ["{command}"],
        },
        "messages": {
            "success": "✅ {target} est autorisé à poster un lien pendant 60 secondes.",
            "usage":   "Usage : !{command} <pseudo>",
        },
    },
    {
        "command_key": "unpermit",
        "label": "Révoquer lien",
        "description": "Retire l'autorisation de poster un lien",
        "default_name": "unpermit",
        "default_role": "mod",
        "tags": {
            "success": ["{target}"],
            "usage":   ["{command}"],
        },
        "messages": {
            "success": "🚫 {target} n'est plus autorisé à poster des liens.",
            "usage":   "Usage : !{command} <pseudo>",
        },
    },
    {
        "command_key": "de",
        "label": "Lancer un dé",
        "description": "Lance un dé aléatoire dans le chat (1-6 par défaut, ou !dé 100)",
        "default_name": "dé",
        "default_aliases": ["de", "dice", "roll"],
        "default_role": "everyone",
        "tags": {
            "result": ["{user}", "{result}", "{max}"],
        },
        "messages": {
            "result": "🎲 @{user} lance le dé et fait {result} sur {max} !",
        },
    },
    {
        "command_key": "uptime",
        "label": "Uptime stream",
        "description": "Affiche depuis combien de temps le stream est en live",
        "default_name": "uptime",
        "default_role": "everyone",
        "tags": {
            "live":    ["{duration}"],
            "offline": [],
        },
        "messages": {
            "live":    "⏱️ Le stream est en live depuis {duration} !",
            "offline": "💤 Le stream n'est pas en live en ce moment.",
        },
    },
    {
        "command_key": "counter",
        "label": "Compteur",
        "description": "Compteur incrémental (morts, victoires…) — !counter +1 / !counter reset / !counter",
        "default_name": "counter",
        "default_role": "mod",
        # Affichage ouvert à tous ; le rôle ci-dessous est celui exigé pour MODIFIER (+1, reset).
        "enforce_role": False,
        "role_note": "Rôle exigé pour modifier le compteur (+1 / reset). L'affichage reste ouvert à tous.",
        "tags": {
            "show":  ["{label}", "{count}"],
            "add":   ["{label}", "{count}", "{delta}"],
            "reset": ["{label}"],
        },
        "messages": {
            "show":  "🔢 {label} : {count}",
            "add":   "🔢 {label} : {count} (+{delta})",
            "reset": "🔄 {label} remis à zéro !",
        },
    },
    {
        "command_key": "setword",
        "label": "Mot secret — définir",
        "description": "Un modo définit le mot secret du mini-jeu ; les viewers le devinent avec la commande « Mot secret — deviner »",
        "default_name": "setword",
        "default_role": "mod",
        "tags": {
            "usage":   ["{user}", "{command}"],
            "success": ["{user}", "{guess_command}"],
        },
        "messages": {
            "usage":   "@{user}, tu dois préciser un mot ! Exemple : !{command} ananas",
            "success": "🤫 Le mot secret a été défini par @{user} ! À vous de le deviner avec !{guess_command} <mot>...",
        },
    },
    {
        "command_key": "guess",
        "label": "Mot secret — deviner",
        "description": "Les viewers tentent de deviner le mot secret (aucune réponse si le mot est faux, pour ne pas spammer)",
        "default_name": "guess",
        "default_aliases": ["mot"],
        "default_role": "everyone",
        "tags": {
            "no_word": ["{user}"],
            "win":     ["{user}"],
        },
        "messages": {
            "no_word": "@{user}, aucun mot secret n'est défini pour le moment !",
            "win":     "🎉 BINGO ! @{user} a trouvé le mot secret ! Félicitations !",
        },
    },
    {
        "command_key": "game",
        "label": "Infos du jeu (IGDB)",
        "description": "Affiche la fiche du jeu en cours (ou du jeu demandé : !game Nom du jeu), traduite en français",
        "default_name": "game",
        "default_aliases": ["infogame"],
        "default_role": "everyone",
        "tags": {
            "result":       ["{name}", "{developer}", "{date}", "{genres}", "{summary}", "{steam}"],
            "steam":        ["{url}"],
            "no_game":      [],
            "none_running": [],
            "igdb_error":   ["{status}"],
            "not_found":    ["{game}"],
            "error":        [],
        },
        "messages": {
            "result":       "🎮 {name} | 👨‍💻 {developer} | 📅 {date} | 🔖 {genres} | ℹ️ {summary}{steam}",
            "steam":        " | 🌐 Steam: {url}",
            "no_game":      "❌ Aucun jeu spécifié et le stream est actuellement hors ligne.",
            "none_running": "❌ Aucun jeu précis n'est en cours.",
            "igdb_error":   "❌ Impossible de joindre IGDB (Erreur {status})",
            "not_found":    "❌ Aucun jeu trouvé sous le nom '{game}'.",
            "error":        "❌ Une erreur est survenue lors de la recherche IGDB.",
        },
    },
    {
        "command_key": "translate",
        "label": "Traduction (toutes les langues)",
        "description": "Traduit un message dans la langue demandée : !en Bonjour le chat, !es, !de, !ja… (une commande par langue, liste ci-dessous)",
        "default_name": "traduire",
        "default_role": "everyone",
        "name_locked": True,
        "role_note": "Les déclencheurs sont les codes de langue (!en, !es…), non renommables un par un ; le nom « traduire » affiche l'aide.",
        "tags": {
            "help":        ["{commands}", "{example}"],
            "usage":       ["{user}", "{command}"],
            "result":      ["{user}", "{lang}", "{command}", "{text}"],
            "error":       ["{user}"],
            "unavailable": ["{user}"],
        },
        "messages": {
            "help":        "🌍 Traductions disponibles : {commands} — exemple : !{example} Bonjour le chat",
            "usage":       "@{user}, que dois-je traduire ? Exemple : !{command} Bonjour le chat",
            "result":      "🌍 Traduction ({lang}) {user} : {text}",
            "error":       "❌ {user}, erreur lors de la traduction (Problème de connexion).",
            "unavailable": "❌ {user}, service de traduction indisponible.",
        },
    },
    {
        "command_key": "poll",
        "label": "Vote sondage Twitch",
        "description": "Le chat vote sur un sondage / une prédiction Twitch native (!poll 1 à 4). Silencieux par défaut.",
        "default_name": "poll",
        "default_role": "everyone",
        "tags": {"confirm": ["{user}", "{choice}"]},
        "messages": {"confirm": ""},
    },
]

ROLES_ORDER = ["everyone", "sub", "vip", "mod", "broadcaster"]

# ── Cache en mémoire ──────────────────────────────────────────────────────────
_cache: Optional[dict] = None   # {command_key: {command_name, enabled, min_role, messages}}
_cache_at: float = 0.0
CACHE_TTL = 60.0


def invalidate_cache():
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0


def _split_aliases(raw) -> list[str]:
    return [a.strip().lower() for a in (raw or "").replace(";", ",").split(",") if a.strip()]


async def _load_cache():
    global _cache, _cache_at
    from app.core.database import get_db_connection
    async with get_db_connection() as db:
        await db.execute("SELECT command_key, command_name, enabled, min_role, messages, aliases FROM bot_system_commands")
        rows = await db.fetchall()
    _cache = {r["command_key"]: {
        "command_name": r["command_name"],
        "enabled":      bool(r["enabled"]),
        "min_role":     r["min_role"],
        "messages":     json.loads(r["messages"]) if isinstance(r["messages"], str) else (r["messages"] or {}),
        "aliases":      _split_aliases(r["aliases"]),
    } for r in rows}
    _cache_at = time.time()


async def get_all_configs() -> dict:
    global _cache, _cache_at
    if _cache is None or (time.time() - _cache_at) > CACHE_TTL:
        await _load_cache()
    return _cache


async def get_config(command_key: str) -> Optional[dict]:
    cfg = await get_all_configs()
    return cfg.get(command_key)


async def get_config_by_name(command_name: str) -> Optional[tuple[str, dict]]:
    """Retourne (command_key, config) pour un nom de commande donné (nom principal ou alias)."""
    cfg = await get_all_configs()
    wanted = command_name.lower()
    for key, val in cfg.items():
        if val["command_name"].lower() == wanted:
            return key, val
    for key, val in cfg.items():
        if wanted in val.get("aliases", []):
            return key, val
    return None


def definition_of(command_key: str) -> Optional[dict]:
    return next((d for d in SYSTEM_COMMANDS_DEFINITION if d["command_key"] == command_key), None)


def enforces_role(command_key: str) -> bool:
    """Faux pour les commandes qui gèrent elles-mêmes leur rôle (ex. compteur : lecture publique)."""
    d = definition_of(command_key)
    return d.get("enforce_role", True) if d else True


def role_allowed(min_role: str, *, is_owner: bool, is_mod: bool, is_vip: bool, is_sub: bool) -> bool:
    """Le rôle du viewer atteint-il le rôle minimum réglé dans l'admin ? (broadcaster > mod > vip > sub > tous)"""
    level = 4 if is_owner else 3 if is_mod else 2 if is_vip else 1 if is_sub else 0
    try:
        required = ROLES_ORDER.index(min_role)
    except ValueError:
        required = 3      # rôle inconnu : par prudence on exige modo
    return level >= required


async def command_name_of(command_key: str) -> str:
    """Nom actuel (sans !) d'une commande système, tel que réglé dans l'admin."""
    cfg = await get_config(command_key)
    d = definition_of(command_key)
    return (cfg or {}).get("command_name") or (d["default_name"] if d else command_key)


async def msg(command_key: str, field: str, **kwargs) -> str:
    """Retourne le message configuré pour (command_key, field), avec les vars interpolées."""
    cfg = await get_config(command_key)
    defn = next((d for d in SYSTEM_COMMANDS_DEFINITION if d["command_key"] == command_key), None)
    if defn:
        default = defn["messages"].get(field, "")
    else:
        default = ""
    template = (cfg["messages"].get(field) if cfg and cfg["messages"].get(field) else None) or default
    # Remplacement des {variables} connues ; toute autre accolade (faute de frappe, variable inconnue)
    # est laissée telle quelle au lieu de faire planter la commande.
    return re.sub(r"\{(\w+)\}", lambda m: str(kwargs[m.group(1)]) if m.group(1) in kwargs else m.group(0), template)


async def init_system_commands_table():
    from app.core.database import get_db_connection
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_system_commands (
                command_key  VARCHAR(50) PRIMARY KEY,
                command_name VARCHAR(50) NOT NULL UNIQUE,
                enabled      BOOLEAN DEFAULT TRUE,
                min_role     VARCHAR(20) DEFAULT 'mod',
                messages     JSONB NOT NULL DEFAULT '{}'
            )
        """)
        # NULL = "jamais réglé" : les alias par défaut sont posés une seule fois, puis l'admin en garde la main.
        await db.execute("ALTER TABLE bot_system_commands ADD COLUMN IF NOT EXISTS aliases TEXT")
        await db.execute("ALTER TABLE bot_system_commands ADD COLUMN IF NOT EXISTS description TEXT")
        for defn in SYSTEM_COMMANDS_DEFINITION:
            await db.execute("""
                INSERT INTO bot_system_commands (command_key, command_name, enabled, min_role, messages, aliases, description)
                VALUES ($1, $2, TRUE, $3, $4, $5, $6)
                ON CONFLICT (command_key) DO UPDATE
                    SET messages = EXCLUDED.messages
                    WHERE bot_system_commands.messages = '{}'::jsonb
            """, (
                defn["command_key"],
                defn["default_name"],
                defn["default_role"],
                json.dumps(defn["messages"]),
                ",".join(defn.get("default_aliases", [])),
                defn["description"],
            ))
            await db.execute(
                "UPDATE bot_system_commands SET aliases = $1 WHERE command_key = $2 AND aliases IS NULL",
                (",".join(defn.get("default_aliases", [])), defn["command_key"]),
            )
            await db.execute(
                "UPDATE bot_system_commands SET description = $1 WHERE command_key = $2 AND (description IS NULL OR description = '')",
                (defn["description"], defn["command_key"]),
            )

        # Sondage interne du bot (page « Sondages & FAQ ») supprimé le 12/11/2026 : !choix et !sondage n'existent plus.
        await db.execute("DELETE FROM bot_system_commands WHERE command_key IN ('choix', 'sondage')")

        try:
            await _migrate_legacy_play(db)
        except Exception as e:      # ne doit jamais empêcher le démarrage du bot
            logger.error(f"❌ [SYSCMD] Migration !replay/!showtiktok → !play : {e}")



async def _migrate_legacy_play(db) -> None:
    """Fusionne les anciennes commandes « replay » et « showtiktok » dans « play » : reprend leurs
    réglages (rôle, activation, messages — dont le message TikTok réellement utilisé, stocké dans
    discord_features_settings) puis supprime les anciennes lignes, qui masqueraient les alias.
    S'exécute une seule fois : sans anciennes lignes, il n'y a rien à faire."""
    await db.execute(
        "SELECT command_key, enabled, min_role, messages FROM bot_system_commands WHERE command_key IN ('replay', 'showtiktok')"
    )
    legacy = {r["command_key"]: r for r in await db.fetchall()}
    if not legacy:
        return

    def as_dict(raw):
        return json.loads(raw) if isinstance(raw, str) else dict(raw or {})

    defn = next(d for d in SYSTEM_COMMANDS_DEFINITION if d["command_key"] == "play")
    messages = dict(defn["messages"])

    replay_msgs = as_dict(legacy["replay"]["messages"]) if "replay" in legacy else {}
    tiktok_msgs = as_dict(legacy["showtiktok"]["messages"]) if "showtiktok" in legacy else {}
    if replay_msgs.get("playing"):
        messages["clip_playing"] = replay_msgs["playing"]
    for old_key, new_key in (("error_download", "tiktok_download_error"), ("error_no_video", "tiktok_none"),
                             ("error_wrong_account", "tiktok_wrong_account")):
        if tiktok_msgs.get(old_key):
            messages[new_key] = tiktok_msgs[old_key]

    # Le message TikTok réellement affiché dans le chat vient de discord_features_settings (l'ancienne
    # commande ne lisait pas celui de sa carte) : c'est lui qu'on conserve.
    await db.execute("SELECT showtiktok_message FROM discord_features_settings WHERE id = 1")
    live = await db.fetchone()
    if live and live["showtiktok_message"]:
        messages["tiktok_success"] = live["showtiktok_message"]
    elif tiktok_msgs.get("success"):
        messages["tiktok_success"] = tiktok_msgs["success"]

    roles = [legacy[k]["min_role"] for k in legacy if legacy[k]["min_role"] in ROLES_ORDER]
    min_role = max(roles, key=ROLES_ORDER.index) if roles else defn["default_role"]   # le plus strict des deux
    enabled = any(bool(legacy[k]["enabled"]) for k in legacy)

    await db.execute(
        "UPDATE bot_system_commands SET messages = $1, min_role = $2, enabled = $3 WHERE command_key = 'play'",
        (json.dumps(messages), min_role, enabled),
    )
    await db.execute("DELETE FROM bot_system_commands WHERE command_key IN ('replay', 'showtiktok')")
    logger.info(f"🔗 [SYSCMD] !replay et !showtiktok fusionnés dans !play (rôle={min_role}, activée={enabled}).")
