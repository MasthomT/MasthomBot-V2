"""
partners_service.py — Gestion des partenaires FEL-X

Couvre deux origines de partenaires :
  - "manual"     : ajoutés à la main par Thomas via l'admin (amis streamers, recommandations)
  - "guest_star" : détectés automatiquement via EventSub quand quelqu'un rejoint
                   une session Guest Star sur la chaîne

Le statut "en ligne" n'est JAMAIS stocké en base : il est recalculé à chaque
lecture de la page via l'API Twitch (comme déjà fait pour tracked_streamers
dans admin.py). Stocker un booléen "is_live" en base se désynchroniserait
en quelques minutes ; mieux vaut une vérité calculée à la demande.
"""

import logging
import aiohttp
from datetime import datetime, timezone
from typing import Optional

from app.core.database import get_db_connection
from app.core.config import settings

logger = logging.getLogger("masthbot.partners")


# ==========================================
# MIGRATION DE TABLE (à appeler depuis init_db)
# ==========================================

PARTNERS_TABLE_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS partners (
        id SERIAL PRIMARY KEY,
        twitch_login TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        avatar_url TEXT DEFAULT '',
        description TEXT DEFAULT '',
        partnership_type TEXT DEFAULT 'Collab',
        source TEXT NOT NULL DEFAULT 'manual',
        category TEXT NOT NULL DEFAULT 'manual',
        first_collab_at TIMESTAMP DEFAULT NULL,
        last_collab_at TIMESTAMP DEFAULT NULL,
        collab_count INTEGER DEFAULT 0,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,
    "ALTER TABLE partners ADD COLUMN IF NOT EXISTS partnership_type TEXT DEFAULT 'Collab'",
    "ALTER TABLE partners ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual'",
    "ALTER TABLE partners ADD COLUMN IF NOT EXISTS collab_count INTEGER DEFAULT 0",
    "ALTER TABLE partners ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
    # category : regroupe les partenaires affichés sur la page (moderator / recommended / collab / manual)
    "ALTER TABLE partners ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'manual'",
    # "Dernière collab" ne doit refléter QUE les collabs Twitch détectées automatiquement
    # (Guest Star = "Streamez ensemble"), jamais la date d'ajout manuel à la page Partenaires.
    "UPDATE partners SET first_collab_at = NULL, last_collab_at = NULL, collab_count = 0 WHERE source != 'guest_star'",
]

VALID_CATEGORIES = {"moderator", "recommended", "collab", "manual"}


async def run_partners_migrations():
    async with get_db_connection() as conn:
        for query in PARTNERS_TABLE_MIGRATIONS:
            try:
                await conn.execute(query)
            except Exception as e:
                logger.error(f"❌ [PARTNERS INIT] Erreur de migration : {e}")
    logger.info("🤝 [PARTNERS INIT] Table partners synchronisée.")


# ==========================================
# RÉCUPÉRATION D'INFOS TWITCH (avatar, display_name réel)
# ==========================================

async def fetch_twitch_user_info(login: str) -> Optional[dict]:
    """
    Va chercher le display_name et l'avatar réels sur Twitch à partir d'un login.
    Renvoie None si le login n'existe pas ou si l'appel échoue.
    """
    login = login.lower().strip().lstrip("@")
    if not login:
        return None

    url = f"https://api.twitch.tv/helix/users?login={login}"
    headers = {
        "Client-ID": settings.TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {settings.TWITCH_OAUTH_TOKEN.replace('oauth:', '')}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ [PARTNERS] Twitch API a renvoyé {resp.status} pour login={login}")
                    return None
                data = await resp.json()
                users = data.get("data", [])
                if not users:
                    return None
                u = users[0]
                return {
                    "login": u["login"],
                    "display_name": u["display_name"],
                    "avatar_url": u.get("profile_image_url", "")
                }
    except Exception as e:
        logger.error(f"❌ [PARTNERS] Erreur fetch_twitch_user_info({login}): {e}")
        return None


async def check_live_status(logins: list[str]) -> dict[str, bool]:
    """
    Vérifie en une seule requête lesquels de ces logins sont actuellement en live.
    Renvoie {login_lowercase: True/False}.
    """
    result = {login.lower(): False for login in logins}
    if not logins:
        return result

    url = f"https://api.twitch.tv/helix/streams?user_login={'&user_login='.join(logins)}"
    headers = {
        "Client-ID": settings.TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {settings.TWITCH_OAUTH_TOKEN.replace('oauth:', '')}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for stream in data.get("data", []):
                        result[stream["user_login"].lower()] = True
    except Exception as e:
        logger.error(f"❌ [PARTNERS] Erreur check_live_status: {e}")

    return result


# ==========================================
# CRUD MANUEL (admin)
# ==========================================

async def add_partner_manual(
    twitch_login: str,
    description: str = "",
    partnership_type: str = "Collab",
    category: str = "manual"
) -> dict:
    """
    Ajoute un partenaire manuellement depuis l'admin.
    Va chercher automatiquement l'avatar et le display_name réels sur Twitch.
    Si le partenaire existe déjà (même login), met à jour ses infos à la place.

    Ne touche JAMAIS à first_collab_at/last_collab_at/collab_count : ces champs ne
    reflètent que les collabs Twitch détectées automatiquement via Guest Star
    ("Streamez ensemble", voir register_guest_star_collab), pas un ajout manuel.
    """
    twitch_login = twitch_login.lower().strip().lstrip("@")
    if category not in VALID_CATEGORIES:
        category = "manual"

    user_info = await fetch_twitch_user_info(twitch_login)
    if not user_info:
        raise ValueError(f"Le compte Twitch '{twitch_login}' n'a pas été trouvé.")

    async with get_db_connection() as conn:
        existing_cursor = await conn.execute(
            "SELECT id FROM partners WHERE twitch_login = $1", (twitch_login,)
        )
        existing = await existing_cursor.fetchone()

        if existing:
            await conn.execute("""
                UPDATE partners
                SET display_name = $1, avatar_url = $2, description = $3,
                    partnership_type = $4, category = $5, is_active = TRUE
                WHERE twitch_login = $6
            """, (
                user_info["display_name"], user_info["avatar_url"], description,
                partnership_type, category, twitch_login
            ))
        else:
            await conn.execute("""
                INSERT INTO partners
                    (twitch_login, display_name, avatar_url, description, partnership_type, category, source)
                VALUES ($1, $2, $3, $4, $5, $6, 'manual')
            """, (
                twitch_login, user_info["display_name"], user_info["avatar_url"],
                description, partnership_type, category
            ))

    logger.info(f"🤝 [PARTNERS] Partenaire ajouté/mis à jour manuellement : {twitch_login} (catégorie : {category})")
    return user_info


async def register_guest_star_collab(twitch_login: str) -> None:
    """
    Appelée automatiquement quand quelqu'un rejoint une session Guest Star
    (voir eventsub_service.py / handle_guest_star_guest_update).

    Si le partenaire existe déjà (peu importe sa source d'origine), on
    incrémente son compteur de collabs et on met à jour la date.
    S'il n'existe pas, on le crée avec source='guest_star'.
    """
    twitch_login = twitch_login.lower().strip()

    user_info = await fetch_twitch_user_info(twitch_login)
    if not user_info:
        logger.warning(f"⚠️ [PARTNERS] Guest Star détecté pour '{twitch_login}' mais introuvable sur Twitch.")
        return

    async with get_db_connection() as conn:
        existing_cursor = await conn.execute(
            "SELECT id FROM partners WHERE twitch_login = $1", (twitch_login,)
        )
        existing = await existing_cursor.fetchone()

        if existing:
            await conn.execute("""
                UPDATE partners
                SET display_name = $1, avatar_url = $2,
                    first_collab_at = COALESCE(first_collab_at, NOW()), last_collab_at = NOW(),
                    collab_count = collab_count + 1, is_active = TRUE
                WHERE twitch_login = $3
            """, (user_info["display_name"], user_info["avatar_url"], twitch_login))
            logger.info(f"🎙️ [PARTNERS] Guest Star — collab #{1} enregistrée pour partenaire existant : {twitch_login}")
        else:
            await conn.execute("""
                INSERT INTO partners
                    (twitch_login, display_name, avatar_url, description, partnership_type, category, source,
                     first_collab_at, last_collab_at, collab_count)
                VALUES ($1, $2, $3, '', 'Guest Star', 'collab', 'guest_star', NOW(), NOW(), 1)
            """, (twitch_login, user_info["display_name"], user_info["avatar_url"]))
            logger.info(f"🎙️ [PARTNERS] Nouveau partenaire créé via Guest Star : {twitch_login}")


async def remove_partner(partner_id: int) -> None:
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM partners WHERE id = $1", (partner_id,))


async def deactivate_partner(partner_id: int) -> None:
    """Masque un partenaire sans supprimer son historique (collab_count, dates)."""
    async with get_db_connection() as conn:
        await conn.execute("UPDATE partners SET is_active = FALSE WHERE id = $1", (partner_id,))


async def update_partner(
    partner_id: int,
    description: Optional[str] = None,
    partnership_type: Optional[str] = None,
    category: Optional[str] = None
) -> None:
    updates = {}
    if description is not None:
        updates["description"] = description
    if partnership_type is not None:
        updates["partnership_type"] = partnership_type
    if category is not None and category in VALID_CATEGORIES:
        updates["category"] = category

    if not updates:
        return

    set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
    values = tuple(updates.values()) + (partner_id,)

    async with get_db_connection() as conn:
        await conn.execute(f"UPDATE partners SET {set_clause} WHERE id = ${len(values)}", values)


async def _import_logins_as_partners(logins: list[str], category: str, partnership_type: str) -> dict:
    """
    Ajoute une liste de logins Twitch comme partenaires de la catégorie donnée,
    en ignorant ceux déjà présents (peu importe leur catégorie actuelle).
    """
    imported, skipped, failed = [], [], []
    for login in logins:
        async with get_db_connection() as conn:
            existing_cursor = await conn.execute("SELECT id FROM partners WHERE twitch_login = $1", (login,))
            existing = await existing_cursor.fetchone()
        if existing:
            skipped.append(login)
            continue

        user_info = await fetch_twitch_user_info(login)
        if not user_info:
            failed.append(login)
            continue

        async with get_db_connection() as conn:
            await conn.execute("""
                INSERT INTO partners
                    (twitch_login, display_name, avatar_url, description, partnership_type, category, source)
                VALUES ($1, $2, $3, '', $4, $5, 'manual')
                ON CONFLICT (twitch_login) DO NOTHING
            """, (login, user_info["display_name"], user_info["avatar_url"], partnership_type, category))
        imported.append(login)

    return {"imported": imported, "skipped": skipped, "failed": failed}


async def import_from_tracked_streamers() -> dict:
    """
    Reprend les streamers déjà suivis dans le système de notifications de live
    (table tracked_streamers, utilisée pour les annonces Discord) et les ajoute
    comme partenaires "recommandés" — évite de ressaisir à la main des logins
    déjà connus du bot.
    """
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT login FROM tracked_streamers WHERE is_active = 1")
        rows = await cursor.fetchall()
    logins = [r["login"].lower().strip() for r in rows if r["login"]]

    result = await _import_logins_as_partners(logins, category="recommended", partnership_type="Recommandation")
    logger.info(
        f"🤝 [PARTNERS] Import depuis tracked_streamers : {len(result['imported'])} ajoutés, "
        f"{len(result['skipped'])} déjà présents, {len(result['failed'])} échecs."
    )
    return result


async def import_twitch_moderators() -> dict:
    """
    Reprend les modérateurs/rices Twitch (table viewers, colonne is_mod, synchronisée
    chaque heure depuis l'API Twitch) et les ajoute comme partenaires "Modérateur/rice".
    Volontairement Twitch uniquement : les modérateurs Discord sont les mêmes personnes
    (rôle "Gardiens de la Zone"), donc inutile de les importer en double.
    """
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT username FROM viewers WHERE is_mod = 1")
        rows = await cursor.fetchall()
    logins = [r["username"].lower().strip() for r in rows if r["username"]]

    result = await _import_logins_as_partners(logins, category="moderator", partnership_type="Modérateur/rice")
    logger.info(
        f"🤝 [PARTNERS] Import des modérateurs Twitch : {len(result['imported'])} ajoutés, "
        f"{len(result['skipped'])} déjà présents, {len(result['failed'])} échecs."
    )
    return result


# ==========================================
# LECTURE (public + admin)
# ==========================================

async def get_all_partners(include_inactive: bool = False) -> list[dict]:
    """
    Renvoie tous les partenaires avec leur statut live calculé en direct.
    Triés par date de dernière collab (les plus récents en premier).
    """
    async with get_db_connection() as conn:
        if include_inactive:
            cursor = await conn.execute("SELECT * FROM partners ORDER BY last_collab_at DESC NULLS LAST")
        else:
            cursor = await conn.execute(
                "SELECT * FROM partners WHERE is_active = TRUE ORDER BY last_collab_at DESC NULLS LAST"
            )
        rows = await cursor.fetchall()

    partners = [dict(r) for r in rows]
    if not partners:
        return []

    logins = [p["twitch_login"] for p in partners]
    live_status = await check_live_status(logins)

    for p in partners:
        p["is_live"] = live_status.get(p["twitch_login"].lower(), False)
        # asyncpg renvoie des objets datetime, on les sérialise proprement pour le JSON
        for date_field in ("first_collab_at", "last_collab_at", "created_at"):
            if isinstance(p.get(date_field), datetime):
                p[date_field] = p[date_field].isoformat()

    return partners
