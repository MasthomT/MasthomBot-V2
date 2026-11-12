import ast
import logging
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.database import get_db_connection
from app.core.viewer_auth import require_viewer, ensure_self

logger = logging.getLogger("masthbot.api")
router = APIRouter(prefix="/api/v1", tags=["api"])

# ==========================================================
# 🛑 LISTE D'EXCLUSION GLOBALE
# ==========================================================
EXCLUSION_LIST = "('masthou', 'felixthebigblackcat', 'vestale7', 'streamelements', 'wizebot', 'nightbot')"

# ==========================================================
# 1. STATS GLOBALES
# ==========================================================
@router.get("/global_stats")
async def get_global_stats():
    async with get_db_connection() as conn:
        try:
            c1 = await conn.execute(f"SELECT COUNT(*) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}")
            r1 = await c1.fetchone()
            members = r1[0] if r1 else 0

            c2 = await conn.execute(f"SELECT SUM(points) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}")
            r2 = await c2.fetchone()
            total_xp = r2[0] if r2 and r2[0] else 0

            c3 = await conn.execute(f"SELECT MAX(points) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}")
            r3 = await c3.fetchone()
            max_lvl_xp = r3[0] if r3 and r3[0] else 0

            c4 = await conn.execute(f"SELECT username, points FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST} ORDER BY points DESC LIMIT 5")
            top5_raw = await c4.fetchall()
            top5 = [dict(r) for r in top5_raw]

            c5 = await conn.execute(f"""
                SELECT username, first_count, deuz_count, troiz_count
                FROM viewers
                WHERE LOWER(username) NOT IN {EXCLUSION_LIST}
                AND (first_count > 0 OR deuz_count > 0 OR troiz_count > 0)
                ORDER BY first_count DESC, deuz_count DESC, troiz_count DESC
                LIMIT 15
            """)
            podium_raw = await c5.fetchall()
            podium_top = [dict(r) for r in podium_raw]

            return {
                "total_members": members,
                "total_xp": total_xp,
                "max_xp": max_lvl_xp,
                "top5": top5,
                "podium_top": podium_top
            }
        except Exception as e:
            logger.error(f"❌ Erreur global_stats : {e}")
            return {"error": str(e)}

# ==========================================================
# 2. LEADERBOARD
# ==========================================================
@router.get("/leaderboard")
async def get_leaderboard():
    async with get_db_connection() as conn:
        c = await conn.execute(f"SELECT username, points, watchtime FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST} ORDER BY points DESC")
        rows = await c.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            xp = d.get('points', 0)
            d['level'] = max(1, int((xp / 100) ** (1 / 2.2))) if xp > 0 else 1
            result.append(d)
        return result

# ==========================================================
# 2bis. CLASSEMENT TROPHÉES
# ==========================================================
@router.get("/leaderboard/trophies")
async def get_trophies_leaderboard():
    async with get_db_connection() as conn:
        try:
            c = await conn.execute(f"""
                SELECT v.username, COUNT(vt.id) AS trophy_count
                FROM viewer_trophies vt
                JOIN viewers v ON vt.twitch_id = v.twitch_id
                WHERE LOWER(v.username) NOT IN {EXCLUSION_LIST}
                GROUP BY v.username
                ORDER BY trophy_count DESC
                LIMIT 50
            """)
            rows = await c.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"❌ Erreur leaderboard/trophies : {e}")
            return []

# ==========================================================
# 3. SAUVEGARDE FORMULAIRE IA
# ==========================================================
@router.post("/viewer/update_context")
async def update_viewer_context(request: Request):
    # 🔐 Le viewer doit prouver son identité (jeton Twitch) : il ne peut modifier QUE sa propre fiche.
    identity = await require_viewer(request)
    data = await request.json()
    ensure_self(identity, data.get("twitch_id"))
    t_id = identity.user_id
    try:
        async with get_db_connection() as conn:
            c = await conn.execute("SELECT sub_months, is_vip, is_mod FROM viewers WHERE twitch_id = $1", (str(t_id),))
            viewer_check = await c.fetchone()
            
            if not viewer_check:
                raise HTTPException(status_code=404, detail="Viewer introuvable.")
                
            is_sub = viewer_check["sub_months"] and viewer_check["sub_months"] > 0
            is_vip = viewer_check["is_vip"] == 1 or viewer_check["is_vip"] is True
            is_mod = viewer_check["is_mod"] == 1 or viewer_check["is_mod"] is True
            
            if not (is_sub or is_vip or is_mod):
                raise HTTPException(status_code=403, detail="Accès refusé : Fonctionnalité réservée aux abonnés, VIPs et Modérateurs.")

            await conn.execute("""
                UPDATE viewers SET
                    nickname = $1, nickname_for_bot = $2, birthday = $3, sleep_pattern = $4,
                    pronouns = $5, vibe = $6, favorite_game = $7, comfort_game = $8,
                    signature_emote = $9, play_style = $10, useless_talent = $11,
                    favorite_feature = $12, favorite_food = $13, favorite_drink = $14,
                    free_message = $15, roast_level = $16, bot_tone = $17
                WHERE twitch_id = $18
            """, (
                data.get("nickname"), data.get("nickname_for_bot"), data.get("birthday"), data.get("sleep_pattern"),
                data.get("pronouns"), data.get("vibe"), data.get("favorite_game"), data.get("comfort_game"),
                data.get("signature_emote"), data.get("play_style"), data.get("useless_talent"),
                data.get("favorite_feature"), data.get("favorite_food"), data.get("favorite_drink"),
                data.get("free_message"), int(data.get("roast_level") or 5), data.get("bot_tone"), str(t_id)
            ))
        return {"status": "success"}
    except Exception as e:
        import logging
        logger = logging.getLogger("masthbot")
        logger.error(f"❌ [API ERROR] Impossible de sauvegarder le contexte: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})

# ==========================================================
# 6. STREAMERBOT (Récompenses First/Deuz/Troiz)
# ==========================================================
# 🛡️ Garde-fou anti-rafale : un viewer ne peut recevoir qu'UNE SEULE des 3 récompenses
# (first, deuz OU troiz — jamais plusieurs) PAR STREAM. Confirmé le 07/07/2026 après un
# nouveau cas (lehaha25 a réclamé "Deuz" et a reçu les 3 trophées) : les trois positions
# sont mutuellement exclusives pour un même viewer, ce n'est PAS une progression
# cumulative. Streamer.bot semble évaluer ses conditions de seuil en ">=" plutôt qu'en
# "==", donc une fois qu'un viewer a dépassé 1/2/3 messages, il rerenvoie first+deuz+troiz
# en rafale — on ne garde que la toute première réponse, le reste est ignoré. Clé de
# stream = live_id Twitch (settings.personal_last_live_id, déjà suivi par
# live_monitor.py), remis à zéro à chaque nouveau live.
_podium_awarded_by_stream: dict[str, set[str]] = {}

@router.post("/rewards/podium")
async def claim_podium_reward(request: Request):
    try:
        data = await request.json()
        t_id = data.get("twitch_id")
        username = data.get("username")
        reward_type = str(data.get("reward_type", "")).lower()
        count_val = data.get("count")

        if not t_id or reward_type not in ["first", "deuz", "troiz"]:
            return JSONResponse(status_code=400, content={"error": "Données invalides ou type de récompense non géré."})

        t_id = str(t_id)

        async with get_db_connection() as conn:
            c_live = await conn.execute("SELECT personal_last_live_id FROM settings WHERE id = 1")
            live_row = await c_live.fetchone()
            stream_key = (live_row["personal_last_live_id"] if live_row else None) or "no_stream"

            if stream_key not in _podium_awarded_by_stream:
                _podium_awarded_by_stream.clear()  # nouveau stream : on oublie l'ancien
                _podium_awarded_by_stream[stream_key] = set()
            awarded = _podium_awarded_by_stream[stream_key]

            if t_id in awarded:
                return {"status": "ignored", "reason": "ce viewer a déjà reçu une récompense de podium sur ce stream"}
            awarded.add(t_id)

            # Upsert du viewer au cas où il n'existe pas encore
            await conn.execute(
                "INSERT INTO viewers (twitch_id, username, points, messages, watchtime) VALUES ($1, $2, 0, 0, 0) "
                "ON CONFLICT(twitch_id) DO UPDATE SET username = EXCLUDED.username",
                (str(t_id), username)
            )

            col_name = f"{reward_type}_count"

            if count_val is not None and str(count_val).strip().isdigit():
                # Streamer.bot envoie le total exact → on écrase
                exact_count = int(str(count_val).strip())
                await conn.execute(
                    f"UPDATE viewers SET {col_name} = $1 WHERE twitch_id = $2",
                    (exact_count, str(t_id))
                )
            else:
                # Pas de total fourni → on incrémente
                await conn.execute(
                    f"UPDATE viewers SET {col_name} = COALESCE({col_name}, 0) + 1 WHERE twitch_id = $1",
                    (str(t_id),)
                )

        return {"status": "success"}

    except Exception as e:
        logger.error(f"❌ Erreur Podium Reward : {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ==========================================================
# 7. INFOS CHAÎNE
# ==========================================================
@router.get("/channel-info")
async def api_get_channel_info():
    """API publique pour le site fel-x.icu : renvoie les infos et le planning"""
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT * FROM channel_info WHERE id = 1")
        row = await cursor.fetchone()

        if not row:
            return {"error": "Aucune donnée"}

        info = dict(row)

        try:
            schedule = json.loads(info.get("schedule_json") or "[]")
        except Exception:
            schedule = []
        try:
            rules = json.loads(info.get("rules_json") or "[]")
        except Exception:
            rules = []

        return {
            "about_text": info.get("about_text", ""),
            "social_discord": info.get("social_discord", ""),
            "social_youtube": info.get("social_youtube", ""),
            "social_twitch": info.get("social_twitch", ""),
            "social_tiktok": info.get("social_tiktok", ""),
            "social_tips": info.get("social_tips", ""),
            "rules": rules,
            "schedule": schedule
        }
