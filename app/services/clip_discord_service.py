"""
clip_discord_service.py

Détecte les clips Twitch créés pendant le stream et les envoie automatiquement
sur Discord via webhook à la fin du live.
"""

import asyncio
import aiohttp
import logging

logger = logging.getLogger("masthbot.clip_discord")


async def run_clip_discord_migrations():
    from app.core.database import get_db_connection
    async with get_db_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS discord_notified_clips (
                clip_id    TEXT PRIMARY KEY,
                notified_at TIMESTAMP DEFAULT NOW()
            )
        """)
    logger.info("🎬 [CLIP_DISCORD] Table discord_notified_clips synchronisée.")


async def process_new_clips_for_discord(
    broadcaster_id: str,
    webhook_url: str,
    client_id: str,
    token: str,
    since_minutes: int = 360,
):
    """
    Récupère les clips récents du broadcaster, filtre ceux déjà notifiés,
    et envoie chaque nouveau clip sur Discord via webhook.
    """
    from app.core.database import get_db_connection

    headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession() as session:
        # 1. Récupérer les clips récents (jusqu'à 20, triés par date de création)
        clips_url = (
            f"https://api.twitch.tv/helix/clips"
            f"?broadcaster_id={broadcaster_id}&first=20"
        )
        try:
            async with session.get(clips_url, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"❌ [CLIP_DISCORD] Erreur API clips : {resp.status}")
                    return
                data = await resp.json()
                clips = data.get("data", [])
        except Exception as e:
            logger.error(f"❌ [CLIP_DISCORD] Impossible de récupérer les clips : {e}")
            return

        if not clips:
            logger.info("🎬 [CLIP_DISCORD] Aucun clip trouvé pour ce stream.")
            return

        # 2. Filtrer les clips déjà notifiés
        async with get_db_connection() as conn:
            rows = await (await conn.execute("SELECT clip_id FROM discord_notified_clips")).fetchall()
            already_notified = {r["clip_id"] for r in rows}

        new_clips = [c for c in clips if c["id"] not in already_notified]

        if not new_clips:
            logger.info("🎬 [CLIP_DISCORD] Tous les clips ont déjà été notifiés.")
            return

        logger.info(f"🎬 [CLIP_DISCORD] {len(new_clips)} nouveau(x) clip(s) à poster sur Discord.")

        # 3. Récupérer les avatars des créateurs (batch)
        creator_ids = list({c["creator_id"] for c in new_clips})
        creator_info = {}
        try:
            users_url = "https://api.twitch.tv/helix/users?" + "&".join(f"id={uid}" for uid in creator_ids)
            async with session.get(users_url, headers=headers) as resp:
                if resp.status == 200:
                    users_data = await resp.json()
                    for u in users_data.get("data", []):
                        creator_info[u["id"]] = {
                            "name": u["display_name"],
                            "avatar": u["profile_image_url"],
                        }
        except Exception as e:
            logger.warning(f"⚠️ [CLIP_DISCORD] Impossible de récupérer les avatars : {e}")

        # 4. Envoyer chaque clip sur Discord
        for clip in new_clips:
            creator_id  = clip["creator_id"]
            creator_name  = creator_info.get(creator_id, {}).get("name", clip["creator_name"])
            creator_avatar = creator_info.get(creator_id, {}).get("avatar", "")
            clip_url  = clip["url"]
            clip_title = clip["title"]

            payload = {
                "content":     clip_url,
                "username":    creator_name,
                "avatar_url":  creator_avatar,
                "thread_name": clip_title,
                "embeds":      None,
                "attachments": [],
            }

            try:
                async with session.post(webhook_url, json=payload) as resp:
                    if resp.status in (200, 204):
                        logger.info(f"✅ [CLIP_DISCORD] Clip posté : '{clip_title}' par {creator_name}")
                        async with get_db_connection() as conn:
                            await conn.execute(
                                "INSERT INTO discord_notified_clips (clip_id) VALUES ($1) ON CONFLICT DO NOTHING",
                                (clip["id"],)
                            )
                    else:
                        body = await resp.text()
                        logger.error(f"❌ [CLIP_DISCORD] Erreur webhook Discord {resp.status} : {body}")
            except Exception as e:
                logger.error(f"❌ [CLIP_DISCORD] Exception webhook : {e}")

            # Petite pause pour ne pas flood le webhook Discord (rate limit)
            await asyncio.sleep(1.5)
