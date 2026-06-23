import asyncio
import logging
import json
import aiohttp
from datetime import datetime

from app.repositories import viewer_repo
from app.services.twitch_service import twitch_bot
from app.routes.overlays import trigger_overlay_event
from app.services.discord_service import send_message_to_discord
from app.core.config import settings
from app.core.database import get_db_connection

RARE_TIERS = {"Or", "Platine", "Diamant"}

logger = logging.getLogger("masthbot.trophies")

async def auto_trophy_routine():
    """Scanne les viewers pour décerner les trophées selon TOUTES les stats exhaustives du panel."""
    logger.info("🏆 [TROPHY ENGINE] Démarrage du moteur de succès universel.")
    
    await asyncio.sleep(15)

    while True:
        try:
            async with get_db_connection() as conn:
                c1 = await conn.execute("""
                    SELECT * FROM trophy_list 
                    WHERE condition_type != 'none' 
                    AND condition_value > 0
                """)
                rules_raw = await c1.fetchall()
                rules = [dict(r) for r in rules_raw]
                
                winners = []
                
                # 🛡️ LISTE BLANCHE
                valid_cols_direct = [
                    'messages', 'messages_session', 'emotes_global', 'commands_global',
                    'points', 'points_session', 'watchtime', 'watchtime_session', 'streak_days',
                    'gifts_count', 'gifts_session', 'bits_count', 'sub_months', 'rewards_claimed', 'is_vip',
                    'first_count', 'deuz_count', 'troiz_count', 'bombs_won', 'bombs_lost', 'words_guessed',
                    'roast_level', 'ai_prompts', 'is_mod', 'is_artist',
                    'games_rank_s_count', 'games_rank_a_count', 'games_rank_b_count', 'games_rank_c_count',
                    'poll_votes_count', 'questions_asked_count'
                ]
                
                for rule in rules:
                    t_id = rule['id']
                    c_type = rule['condition_type']
                    c_val = rule['condition_value']
                    
                    target_col = c_type
                    target_val = c_val
                    custom_where = None
                    
                    if c_type == 'watchtime_h':
                        target_col = 'watchtime'
                        target_val = c_val * 3600
                    elif c_type == 'watchtime_session_m':
                        target_col = 'watchtime_session'
                        target_val = c_val * 60
                    elif c_type == 'level':
                        target_col = 'points'
                        target_val = int(100 * (c_val ** 2.2))
                    elif c_type == 'has_context':
                        custom_where = "(nickname IS NOT NULL OR favorite_game IS NOT NULL OR vibe IS NOT NULL OR useless_talent IS NOT NULL)"
                    elif c_type == 'has_web_login':
                        custom_where = "last_web_login IS NOT NULL"
                    elif c_type == 'is_vip':
                        target_col = 'is_vip'
                        target_val = 1
                    elif c_type == 'is_mod':
                        target_col = 'is_mod'
                        target_val = 1
                    elif c_type == 'is_artist':
                        target_col = 'is_artist'
                        target_val = 1
                    
                    if not custom_where and target_col not in valid_cols_direct: 
                        continue
                    
                    if custom_where:
                        query = f"""
                            SELECT twitch_id, username FROM viewers 
                            WHERE {custom_where}
                            AND twitch_id NOT IN (SELECT twitch_id FROM viewer_trophies WHERE trophy_id = ?)
                        """
                        c_elig = await conn.execute(query, (t_id,))
                    else:
                        query = f"""
                            SELECT twitch_id, username FROM viewers 
                            WHERE {target_col} >= ? 
                            AND twitch_id NOT IN (SELECT twitch_id FROM viewer_trophies WHERE trophy_id = ?)
                        """
                        c_elig = await conn.execute(query, (target_val, t_id))
                        
                    eligible = await c_elig.fetchall()
                    
                    for v in eligible:
                        await conn.execute("INSERT INTO viewer_trophies (twitch_id, trophy_id) VALUES (?, ?)", (v['twitch_id'], t_id))
                        winners.append({"twitch_id": v['twitch_id'], "username": v['username'], "rule": dict(rule)})

                for w in winners:
                    r = w['rule']
                    bonus_xp = r.get('reward_exp', 0)
                    event_details = f"A débloqué le succès : {r['icon']} {r['label']} !"

                    if bonus_xp > 0:
                        event_details += f" 🎁 (+{bonus_xp} EXP)"
                        # add_experience est déjà une fonction async qui gère la DB, 
                        # pas besoin de la mettre dans le bloc conn.execute courant.
                        await viewer_repo.add_experience(str(w['twitch_id']), w['username'], bonus_xp, "TROPHY", f"Succès : {r['label']}")

                    details_json = json.dumps({"reason": event_details, "source": "Félix (Haut Fait)"}, ensure_ascii=False)
                    
                    # CORRECTION : Syntaxe PostgreSQL ($1, $2, $3) et tuple ( )
                    await conn.execute(
                        "INSERT INTO stream_events (event_type, username, details, timestamp) VALUES ($1, $2, $3, NOW())",
                        ("reward", w['username'], details_json)
                    )
                    
                    # 1. ENVOI DE L'ANIMATION OBS
                    try:
                        payload = {
                            "type": "trophy_unlock",
                            "details": {
                                "username": w['username'],
                                "trophy_name": r['label'],
                                "icon": r['icon'],
                                "tier": r.get('tier', 'Standard')
                            }
                        }
                        await trigger_overlay_event(payload)
                    except Exception as e:
                        logger.error(f"❌ Erreur Overlay Trophée : {e}")
                    
                    # 2. ENVOI DU MESSAGE DANS LE CHAT TWITCH 💬
                    try:
                        tier = r.get('tier', 'Standard')
                        tier_emojis = {
                            'Standard': '🎖️',
                            'Bronze': '🥉',
                            'Argent': '🥈',
                            'Or': '🥇',
                            'Platine': '💠',
                            'Diamant': '💎'
                        }
                        emoji = tier_emojis.get(tier, '🎖️')
                        
                        channel_name = settings.TWITCH_CHANNEL.replace("#", "").lower()
                        channel = twitch_bot.get_channel(channel_name)
                        
                        if channel:
                            msg = f"✨ DING ! @{w['username']} vient de débloquer le Haut Fait {emoji} {r['label']} {r['icon']} ! GG ! 🎉"
                            if bonus_xp > 0:
                                msg += f" (+{bonus_xp} EXP)"
                            await channel.send(msg)
                    except Exception as e:
                        logger.error(f"❌ Erreur annonce chat Trophée : {e}")

                    # 3. ANNONCE DISCORD POUR LES TROPHÉES RARES 💎
                    try:
                        tier = r.get('tier', 'Standard')
                        if tier in RARE_TIERS and settings.TROPHY_DISCORD_CHANNEL_ID:
                            tier_emojis = {'Or': '🥇', 'Platine': '💠', 'Diamant': '💎'}
                            emoji = tier_emojis.get(tier, '🏆')
                            discord_msg = f"{emoji} **{w['username']}** vient de débloquer le succès **{tier}** : {r['icon']} {r['label']} !"
                            if bonus_xp > 0:
                                discord_msg += f" (+{bonus_xp} EXP)"
                            await send_message_to_discord(settings.TROPHY_DISCORD_CHANNEL_ID, discord_msg)
                    except Exception as e:
                        logger.error(f"❌ Erreur annonce Discord Trophée : {e}")

                    logger.info(f"🎉 [HAUT FAIT] {w['username']} a gagné '{r['label']}' !")

        except Exception as e:
            logger.error(f"❌ [TROPHY ENGINE] Erreur dans la boucle principale : {e}")

        await asyncio.sleep(300)

async def start_trophy_engine():
    await auto_trophy_routine()
