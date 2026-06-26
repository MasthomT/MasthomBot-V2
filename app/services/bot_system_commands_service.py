"""
app/services/bot_system_commands_service.py

Gestion des commandes système du bot (so, raidqui, level, etc.).
- Stocke nom, activation, rôle min, messages dans la DB
- Cache en mémoire avec TTL 60s (invalidé manuellement à la sauvegarde admin)
- Fournit le helper msg(key, field, **vars) pour interpoler les messages
"""

import json
import time
import logging
from typing import Optional

logger = logging.getLogger("masthbot.syscmds")

# ── Définition de toutes les commandes système ──────────────────────────────
# command_key  : identifiant interne immuable (= nom du décorateur twitchio)
# label        : nom affiché dans l'admin
# description  : à quoi ça sert
# default_name : déclencheur par défaut (!so, !raidqui, …)
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
        "command_key": "replay",
        "label": "Replay clip",
        "description": "Affiche un clip sur l'overlay et annonce le titre + lien dans le chat",
        "default_name": "replay",
        "default_role": "mod",
        "tags": {
            "playing": ["{title}", "{url}", "{broadcaster}"],
            "extra":   ["{user}"],
        },
        "messages": {
            "playing": "🎬 Replay : {title} — twitch.tv/{broadcaster} ({url})",
            "extra":   "",
        },
    },
    {
        "command_key": "showtiktok",
        "label": "Show TikTok",
        "description": "Affiche un TikTok sur l'overlay (lien ou dernier connu)",
        "default_name": "showtiktok",
        "default_role": "mod",
        "tags": {
            "success":             ["{title}", "{url}"],
            "error_no_video":      [],
            "error_download":      [],
            "error_wrong_account": ["{broadcaster}", "{tiktok_account}"],
        },
        "messages": {
            "success":             "🎵 TikTok affiché à l'écran ! — {title} {url}",
            "error_no_video":      "❌ Aucune vidéo TikTok connue pour le moment.",
            "error_download":      "❌ Impossible de récupérer cette vidéo TikTok. Vérifie le lien !",
            "error_wrong_account": "❌ Seul @{broadcaster} peut afficher un TikTok d'un autre compte. Les modérateurs sont limités au compte @{tiktok_account}.",
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
        "command_key": "sondage",
        "label": "Afficher sondage",
        "description": "Affiche le sondage actif sur l'overlay + résultats dans le chat",
        "default_name": "sondage",
        "default_role": "everyone",
        "tags": {
            "no_poll": [],
        },
        "messages": {
            "no_poll": "🐾 Aucun sondage en cours. Crée-en un sur ton interface admin !",
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
        "command_key": "raidqui",
        "label": "Roulette Raid",
        "description": "Lance la roulette pour choisir qui raider parmi les partners en live",
        "default_name": "raidqui",
        "default_role": "mod",
        "tags": {
            "launch":      ["{count}"],
            "result":      ["{name}", "{login}"],
            "no_partners": [],
            "no_live":     [],
            "error":       [],
        },
        "messages": {
            "launch":      "🎰 Lancement de la roulette raid avec {count} streameur(s) en live...",
            "result":      "🎯 La roulette a choisi : {name} ! Allez les voir sur twitch.tv/{login} PogChamp",
            "no_partners": "❌ Aucun partenaire dans la liste !",
            "no_live":     "😴 Aucun partenaire en live en ce moment !",
            "error":       "❌ Impossible de vérifier les streameurs en live.",
        },
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


async def _load_cache():
    global _cache, _cache_at
    from app.core.database import get_db_connection
    async with get_db_connection() as db:
        await db.execute("SELECT command_key, command_name, enabled, min_role, messages FROM bot_system_commands")
        rows = await db.fetchall()
    _cache = {r["command_key"]: {
        "command_name": r["command_name"],
        "enabled":      bool(r["enabled"]),
        "min_role":     r["min_role"],
        "messages":     json.loads(r["messages"]) if isinstance(r["messages"], str) else (r["messages"] or {}),
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
    """Retourne (command_key, config) pour un nom de commande donné."""
    cfg = await get_all_configs()
    for key, val in cfg.items():
        if val["command_name"].lower() == command_name.lower():
            return key, val
    return None


async def msg(command_key: str, field: str, **kwargs) -> str:
    """Retourne le message configuré pour (command_key, field), avec les vars interpolées."""
    cfg = await get_config(command_key)
    defn = next((d for d in SYSTEM_COMMANDS_DEFINITION if d["command_key"] == command_key), None)
    if defn:
        default = defn["messages"].get(field, "")
    else:
        default = ""
    template = (cfg["messages"].get(field) if cfg and cfg["messages"].get(field) else None) or default
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


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
        for defn in SYSTEM_COMMANDS_DEFINITION:
            await db.execute("""
                INSERT INTO bot_system_commands (command_key, command_name, enabled, min_role, messages)
                VALUES ($1, $2, TRUE, $3, $4)
                ON CONFLICT (command_key) DO UPDATE
                    SET messages = EXCLUDED.messages
                    WHERE bot_system_commands.messages = '{}'::jsonb
            """, (
                defn["command_key"],
                defn["default_name"],
                defn["default_role"],
                json.dumps(defn["messages"]),
            ))
