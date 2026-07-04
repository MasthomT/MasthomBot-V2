import os
import re
import json
import asyncio
import logging
from datetime import datetime, timedelta

from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.vip_sound")

# Mêmes conventions que l'upload admin existant (app/routes/admin_commands.py)
SOUNDS_DIR = "static/commands/sounds"
ALLOWED_SOUNDS = {".mp3", ".wav", ".ogg"}
MAX_SOUND_SIZE = 5 * 1024 * 1024  # 5 Mo
MONTHLY_COOLDOWN_DAYS = 30


async def init_vip_sound_tables() -> None:
    async with get_db_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS vip_sound_requests (
                id           SERIAL PRIMARY KEY,
                twitch_id    TEXT NOT NULL,
                username     TEXT NOT NULL,
                filename     TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'pending',
                submitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
                reviewed_at  TIMESTAMP
            )
        """)
        await conn.execute("ALTER TABLE custom_commands ADD COLUMN IF NOT EXISTS vip_owner_twitch_id TEXT")


def _trigger_names(username: str) -> tuple[str, str | None]:
    """Nom principal = pseudo complet (unique, sert de clé sûre pour custom_commands.name).
    Alias court = pseudo sans les chiffres, seulement s'il diffère (ex: kovix20 -> !kovix20 + !kovix)."""
    full = username.lower().strip()
    base = re.sub(r"\d+", "", full)
    base = re.sub(r"[_\-. ]+", "_", base).strip("_.- ")
    if base and base != full:
        return full, base
    return full, None


async def get_viewer_vip_status(twitch_id: str) -> dict:
    """Statut d'éligibilité + demande en cours, pour l'affichage sur /profile.
    Ouvert aux VIP ET aux modérateurs (le champ reste nommé "is_vip" pour ne pas casser
    le contrat déjà utilisé par le frontend fel-x.icu, mais couvre aussi is_mod)."""
    async with get_db_connection() as conn:
        c = await conn.execute("SELECT is_vip, is_mod FROM viewers WHERE twitch_id = $1", (twitch_id,))
        row = await c.fetchone()
        if not row or not (row["is_vip"] or row["is_mod"]):
            return {"is_vip": False}

        c2 = await conn.execute(
            "SELECT id, filename, status, submitted_at, reviewed_at FROM vip_sound_requests "
            "WHERE twitch_id = $1 ORDER BY submitted_at DESC LIMIT 1",
            (twitch_id,)
        )
        last_row = await c2.fetchone()
        last = dict(last_row) if last_row else None
        for k in ("submitted_at", "reviewed_at"):
            if last and last.get(k):
                last[k] = last[k].isoformat()

        # Quota mensuel : seule une demande APPROUVÉE consomme le mois (un rejet ne compte pas).
        c3 = await conn.execute(
            "SELECT submitted_at FROM vip_sound_requests WHERE twitch_id = $1 AND status = 'approved' "
            "ORDER BY submitted_at DESC LIMIT 1",
            (twitch_id,)
        )
        last_approved = await c3.fetchone()
        next_eligible_at = None
        if last_approved:
            next_eligible_at = last_approved["submitted_at"] + timedelta(days=MONTHLY_COOLDOWN_DAYS)

        can_submit = not next_eligible_at or datetime.now() >= next_eligible_at
        return {
            "is_vip": True,
            "last_request": last,
            "can_submit": can_submit,
            "next_eligible_at": next_eligible_at.isoformat() if next_eligible_at else None,
        }


async def submit_vip_sound(twitch_id: str, username: str, filename_hint: str, file_bytes: bytes) -> dict:
    ext = os.path.splitext(filename_hint or "")[1].lower()
    if ext not in ALLOWED_SOUNDS:
        return {"error": f"Format non supporté ({ext or '?'}). Formats acceptés : mp3, wav, ogg."}
    if len(file_bytes) > MAX_SOUND_SIZE:
        return {"error": "Fichier trop volumineux (5 Mo max)."}

    status = await get_viewer_vip_status(twitch_id)
    if not status.get("is_vip"):
        return {"error": "Réservé aux VIP."}
    if not status.get("can_submit"):
        return {"error": "Tu as déjà un son validé ce mois-ci. Réessaie plus tard."}

    os.makedirs(SOUNDS_DIR, exist_ok=True)
    safe_filename = f"vip_{twitch_id}_{int(datetime.now().timestamp())}{ext}"
    dest = os.path.join(SOUNDS_DIR, safe_filename)
    with open(dest, "wb") as f:
        f.write(file_bytes)

    async with get_db_connection() as conn:
        # Une seule demande "pending" à la fois : une nouvelle soumission remplace l'ancienne.
        c = await conn.execute(
            "SELECT id, filename FROM vip_sound_requests WHERE twitch_id = $1 AND status = 'pending'",
            (twitch_id,)
        )
        existing = await c.fetchone()
        if existing:
            old_path = os.path.join(SOUNDS_DIR, existing["filename"])
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass
            await conn.execute(
                "UPDATE vip_sound_requests SET filename = $1, submitted_at = NOW(), status = 'pending', reviewed_at = NULL WHERE id = $2",
                (safe_filename, existing["id"])
            )
        else:
            await conn.execute(
                "INSERT INTO vip_sound_requests (twitch_id, username, filename) VALUES ($1, $2, $3)",
                (twitch_id, username, safe_filename)
            )
    return {"status": "ok"}


async def list_pending_requests() -> list[dict]:
    async with get_db_connection() as conn:
        c = await conn.execute(
            "SELECT * FROM vip_sound_requests WHERE status = 'pending' ORDER BY submitted_at ASC"
        )
        rows = await c.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("submitted_at"):
                d["submitted_at"] = d["submitted_at"].isoformat()
            result.append(d)
        return result


async def approve_request(request_id: int, chat_message: str = "") -> dict:
    async with get_db_connection() as conn:
        c = await conn.execute("SELECT * FROM vip_sound_requests WHERE id = $1", (request_id,))
        req_row = await c.fetchone()
        if not req_row:
            return {"error": "Demande introuvable."}
        req = dict(req_row)

        full, base = _trigger_names(req["username"])

        # L'alias court n'est posé que s'il n'entre pas en collision avec une commande existante.
        alias = ""
        if base:
            c2 = await conn.execute(
                "SELECT 1 FROM custom_commands WHERE name = $1 OR $1 = ANY(string_to_array(replace(aliases,' ',''), ','))",
                (base,)
            )
            if not await c2.fetchone():
                alias = base
            else:
                logger.warning(f"[VIP SOUND] Alias '{base}' déjà pris, commande de {req['username']} créée sans alias court.")

        response_payload = json.dumps({"text": chat_message or "", "sound": req["filename"]})

        await conn.execute("""
            INSERT INTO custom_commands
                (name, aliases, type, response, cooldown_global, cooldown_user,
                 min_role, is_active, created_by, category, vip_owner_twitch_id)
            VALUES ($1, $2, 'multi', $3, 10, 30, 'viewer', TRUE, 'vip_sound', 'Perso VIP', $4)
            ON CONFLICT (name) DO UPDATE SET
                aliases            = EXCLUDED.aliases,
                response           = EXCLUDED.response,
                is_active          = TRUE,
                vip_owner_twitch_id= EXCLUDED.vip_owner_twitch_id,
                updated_at         = NOW()
        """, (full, alias, response_payload, req["twitch_id"]))

        await conn.execute(
            "UPDATE vip_sound_requests SET status = 'approved', reviewed_at = NOW() WHERE id = $1",
            (request_id,)
        )
    trigger = f"!{full}" + (f" / !{alias}" if alias else "")
    return {"status": "ok", "trigger": trigger}


async def reject_request(request_id: int) -> dict:
    async with get_db_connection() as conn:
        c = await conn.execute("SELECT * FROM vip_sound_requests WHERE id = $1", (request_id,))
        req_row = await c.fetchone()
        if not req_row:
            return {"error": "Demande introuvable."}
        req = dict(req_row)
        path = os.path.join(SOUNDS_DIR, req["filename"])
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        await conn.execute(
            "UPDATE vip_sound_requests SET status = 'rejected', reviewed_at = NOW() WHERE id = $1",
            (request_id,)
        )
    return {"status": "ok"}


async def sync_vip_command_status_loop():
    """Boucle périodique : désactive/réactive automatiquement les commandes perso VIP
    selon le statut VIP OU modérateur actuel du viewer (perte des deux -> commande
    désactivée, sans être supprimée ; garde l'un des deux statuts -> reste active)."""
    logger.info("🎟️ [VIP SOUND] Démarrage de la synchro statut VIP/Mod ↔ commandes perso.")
    await asyncio.sleep(20)
    while True:
        try:
            async with get_db_connection() as conn:
                await conn.execute("""
                    UPDATE custom_commands cc
                    SET is_active = (v.is_vip = 1 OR v.is_mod = 1)
                    FROM viewers v
                    WHERE cc.vip_owner_twitch_id = v.twitch_id
                    AND cc.is_active != (v.is_vip = 1 OR v.is_mod = 1)
                """)
        except Exception as e:
            logger.error(f"❌ [VIP SOUND] Erreur synchro statut VIP/Mod : {e}")
        await asyncio.sleep(600)
