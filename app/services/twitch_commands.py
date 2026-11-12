"""Commandes de chat du bot Twitch (!so, !play, !vip, !timer…) — mélangées à MasthbotTwitch."""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from twitchio.ext import commands

from app.core.config import settings
from app.services.notification_service import notification_service
from app.core.database import get_db_connection
from app.routes.clips import start_clips_poll
from app.services.twitch_common import safe_send, classify_play_input, _TIKTOK_LINK_RE, _permitted_users

logger = logging.getLogger("masthbot.twitch")


class ChatCommandsMixin:
    @commands.command(name='so')
    async def shoutout_command(self, ctx, *, content: str = None):
        # Rôle minimum contrôlé en amont (admin > Commandes).
        from app.services.bot_system_commands_service import msg as syscmd_msg, get_config
        syscmd_cfg = await get_config("so")
        cmd_label = syscmd_cfg["command_name"] if syscmd_cfg else "so"
        if not content:
            return await ctx.send(await syscmd_msg("so", "usage", command=cmd_label))

        input_val = content.replace("!so", "").strip().split()[0].split("?")[0]
        target_name = None
        slug_for_node = None

        client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}
        session = await self.get_web_session()

        if "twitch.tv" in input_val:
            if "clips.twitch.tv" in input_val:
                slug_for_node = input_val.split("clips.twitch.tv/")[-1].strip("/")
                try:
                    async with session.get(f"https://api.twitch.tv/helix/clips?id={slug_for_node}", headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("data"):
                                target_name = data["data"][0]["broadcaster_name"]
                except: pass

            elif "/clip/" in input_val:
                parts = input_val.split("twitch.tv/")[-1].strip("/").split("/")
                target_name = parts[0]
                slug_for_node = parts[2] if len(parts) >= 3 else None

            elif "/videos/" in input_val:
                video_id = input_val.split("/videos/")[-1].strip("/")
                try:
                    async with session.get(f"https://api.twitch.tv/helix/videos?id={video_id}", headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("data"):
                                target_name = data["data"][0]["user_name"]
                except: pass
            else:
                target_name = input_val.split("twitch.tv/")[-1].strip("/")
        else:
            target_name = input_val.replace("@", "")

        if not target_name:
            return await ctx.send(await syscmd_msg("so", "error_url"))

        target_name_clean = target_name.lower()
        
        try:
            async with session.get(f"https://api.twitch.tv/helix/users?login={target_name_clean}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("data"):
                        s_id = data["data"][0]["id"]
                        s_display = data["data"][0]["display_name"]
                        async with session.get(f"https://api.twitch.tv/helix/channels?broadcaster_id={s_id}", headers=headers) as c_resp:
                            last_game = "un jeu inconnu"
                            if c_resp.status == 200:
                                c_data = await c_resp.json()
                                if c_data.get("data") and c_data["data"][0].get("game_name"):
                                    last_game = c_data["data"][0]["game_name"]
                            
                            await ctx.send(await syscmd_msg("so", "success", target=s_display, game=last_game, url=f"https://twitch.tv/{target_name_clean}"))
                    else:
                        await ctx.send(await syscmd_msg("so", "success_basic", target=target_name, url=f"https://twitch.tv/{target_name_clean}"))
        except Exception as e:
            logger.error(f"❌ [SHOUTOUT] Échec récupération infos pour {target_name_clean} : {e}")
            await ctx.send(await syscmd_msg("so", "success_basic", target=target_name, url=f"https://twitch.tv/{target_name_clean}"))

        try:
            async with session.post(f"{settings.OVERLAY_NODE_URL}/api/shoutout", json={"target": target_name_clean, "slug": slug_for_node}) as _:
                pass
        except Exception as e:
            logger.error(f"Erreur Envoi SO Node : {e}")

    @commands.command(name='play')
    async def cmd_play(self, ctx, *, content: str = None):
        """Lecteur unifié : un clip Twitch (lien, titre, ou rien = le dernier), un TikTok, une vidéo YouTube ou Instagram.
        Le nom, les alias, le rôle et les messages se règlent dans l'admin (Commandes)."""
        kind, value = classify_play_input(content)
        if kind in ("tiktok", "video"):
            await self._play_tiktok(ctx, value)
        else:
            await self._play_clip(ctx, value["slug"], value["query"])

    async def _play_clip(self, ctx, slug, query):
        session = await self.get_web_session()

        from app.services.bot_system_commands_service import msg as syscmd_msg
        client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}

        # Résoudre le slug depuis le lien ou la recherche
        resolved_slug = slug
        if slug and "twitch.tv" in slug:
            # Extraire le slug depuis une URL clip
            if "/clip/" in slug:
                resolved_slug = slug.split("/clip/")[-1].split("?")[0]
            elif "clips.twitch.tv/" in slug:
                resolved_slug = slug.split("clips.twitch.tv/")[-1].split("?")[0]

        clip_title = None
        clip_url = None
        clip_broadcaster = None

        # Si on a un slug direct, on récupère les infos
        if resolved_slug and "/" not in resolved_slug:
            try:
                async with session.get(
                    f"https://api.twitch.tv/helix/clips?id={resolved_slug}",
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("data"):
                            c = data["data"][0]
                            clip_title = c.get("title", "")
                            clip_url = c.get("url", f"https://clips.twitch.tv/{resolved_slug}")
                            clip_broadcaster = c.get("broadcaster_name", "")
            except Exception as e:
                logger.warning(f"⚠️ [PLAY] Impossible de récupérer les infos du clip : {e}")

        try:
            payload = {"slug": resolved_slug or slug, "query": query}
            async with session.post(f"{settings.OVERLAY_NODE_URL}/api/replay", json=payload) as resp:
                node_data = await resp.json() if resp.content_type == "application/json" else {}

            if node_data.get("status") == "not_found":
                reply = await syscmd_msg("play", "clip_not_found")
                if reply:
                    await safe_send(ctx.channel, reply)
                return

            # Si Node.js a choisi le clip (mode query), on récupère les infos depuis sa réponse
            if not clip_title and node_data.get("title"):
                clip_title = node_data["title"]
                clip_broadcaster = node_data.get("creator", clip_broadcaster or self.channel_name)
                clip_url = node_data.get("url") or (
                    f"https://clips.twitch.tv/{node_data['clip_id']}" if node_data.get("clip_id") else None
                )

            # (le son d'alerte est déjà joué par le serveur Node au moment de lancer le clip)

            # Message chat si titre disponible
            if clip_title:
                reply = await syscmd_msg("play", "clip_playing",
                    title=clip_title,
                    url=clip_url or "",
                    broadcaster=clip_broadcaster or self.channel_name)
                if reply:
                    await safe_send(ctx.channel, reply)

        except Exception as e:
            logger.error(f"❌ [PLAY ERROR] clip : {e}")

    async def _play_tiktok(self, ctx, source_url):
        from app.services.bot_system_commands_service import msg as syscmd_msg
        author_badges = ctx.author.badges or {}
        is_owner = (
            ctx.author.is_broadcaster
            or ctx.author.name.lower() == self.channel_name
            or "broadcaster" in author_badges
        )
        is_mod = bool(is_owner or ctx.author.is_mod or "moderator" in author_badges)
        # Rôle minimum (et récompense TikTok Replay) contrôlés en amont (admin > Commandes).

        async with get_db_connection() as conn:
            c = await conn.execute("SELECT tiktok_username FROM discord_features_settings WHERE id = 1")
            row = await c.fetchone()
        channel_tiktok_username = (row["tiktok_username"] if row else "") or ""

        logger.info(f"[PLAY/TIKTOK] is_owner={is_owner} | name={ctx.author.name!r} | url={source_url!r}")

        from app.services.tiktok_monitor import get_last_known_tiktok, get_direct_tiktok_video
        from app.routes.overlays import register_tiktok_proxy

        if not source_url:      # « tiktok » sans lien : le dernier TikTok de la chaîne
            last = await get_last_known_tiktok()
            if not last:
                return await safe_send(ctx.channel, await syscmd_msg("play", "tiktok_none"))
            source_url = last["url"]

        is_tiktok = bool(_TIKTOK_LINK_RE.search(source_url))
        pre = "tiktok" if is_tiktok else "video"      # clés des messages : tiktok_* ou video_*

        logger.info(f"[PLAY/{pre.upper()}] Téléchargement en cours : {source_url}")
        video = await get_direct_tiktok_video(source_url)
        if video and video.get("too_long"):
            minutes = int(video["too_long"] // 60)
            return await safe_send(ctx.channel, await syscmd_msg("play", "video_too_long", duration=f"{minutes} min", max="5 min"))
        if not video:
            logger.error(f"[PLAY/{pre.upper()}] Échec download pour {source_url}")
            return await safe_send(ctx.channel, await syscmd_msg("play", f"{pre}_download_error"))

        logger.info(f"[PLAY/TIKTOK] Vidéo OK : uploader={video.get('uploader')!r} filepath={video.get('filepath')!r}")

        # Seuls les viewers (récompense « TikTok Replay ») sont limités au compte TikTok de la chaîne :
        # les modérateurs et le streamer peuvent lire n'importe quel TikTok.
        if is_tiktok and not is_mod and channel_tiktok_username and video.get("uploader") != channel_tiktok_username.lower():
            try:
                os.remove(video["filepath"])
            except OSError:
                pass
            return await safe_send(ctx.channel, await syscmd_msg(
                "play", "tiktok_wrong_account", broadcaster=self.channel_name, tiktok_account=channel_tiktok_username))

        # Le TikTok passe par la MÊME file d'attente et le MÊME overlay que les clips (serveur Node,
        # page /shoutout) : jamais deux médias à l'écran en même temps.
        token = register_tiktok_proxy(video["filepath"])
        try:
            session = await self.get_web_session()
            async with session.post(
                f"{settings.OVERLAY_NODE_URL}/api/tiktok",
                json={"url": f"/api/v1/tiktok_proxy/{token}", "duration": video.get("duration") or 0,
                      "source": "tiktok" if is_tiktok else ("instagram" if "instagram" in source_url.lower() or "instagr.am" in source_url.lower() else "youtube")},
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
            logger.info(f"[PLAY/TIKTOK] Envoyé à la file de l'overlay avec token={token}")
        except Exception as e:
            logger.error(f"❌ [PLAY/TIKTOK] Impossible d'envoyer le TikTok à l'overlay : {e}")
            return await safe_send(ctx.channel, await syscmd_msg("play", f"{pre}_download_error"))

        reply = await syscmd_msg("play", f"{pre}_success", title=video.get("title") or "", url=source_url)
        if reply:
            await safe_send(ctx.channel, reply)

    @commands.command(name='renotif')
    async def cmd_renotif(self, ctx):
        from app.services.bot_system_commands_service import msg as syscmd_msg
        config = await self.get_db_config()
        channel_id = config.get('notif_live_channel_id')
        if not channel_id:
            return await ctx.send(await syscmd_msg("renotif", "no_channel"))

        streams = await self.fetch_streams(user_logins=[self.channel_name])
        if streams:
            s = streams[0]
            await notification_service.send_discord_live_notification(
                channel_id=channel_id,
                channel_name=self.channel_name,
                title=s.title,
                game=s.game_name,
                custom_message=config.get('discord_notify_message')
            )
            await ctx.send(await syscmd_msg("renotif", "success", game=s.game_name))
        else:
            await ctx.send(await syscmd_msg("renotif", "no_live"))

    @commands.command(name='checkcopains')
    async def cmd_checkcopains(self, ctx):
            
        from app.services.bot_system_commands_service import msg as syscmd_msg
        config = await self.get_db_config()
        channel_id = config.get('streamers_channel_id')
        if not channel_id:
            return await ctx.send(await syscmd_msg("checkcopains", "no_channel"))

        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT * FROM tracked_streamers WHERE is_active=1")
                tracked = await c.fetchall()
        except Exception as e:
            logger.error(f"❌ [DB ERROR] Impossible de lire les copains : {e}")
            return

        if not tracked:
            return await ctx.send(await syscmd_msg("checkcopains", "no_partners"))

        logins = [s["login"] for s in tracked]
        await ctx.send(await syscmd_msg("checkcopains", "scanning", count=len(logins)))

        streams = await self.fetch_streams(user_logins=logins)
        if not streams:
            return await ctx.send(await syscmd_msg("checkcopains", "empty"))

        notified_count = 0
        tracked_by_login = {t["login"].lower(): t for t in tracked}
        async with get_db_connection() as conn:
            for s in streams:
                login = (getattr(s.user, "login", None) or s.user.name or "").lower()
                partner_msg = f"**{s.user.name}** est en live sur **{{CATEGORIE}}**, foncez lui donner de la force !"
                msg_id = await notification_service.send_discord_live_notification(
                    channel_id=channel_id,
                    channel_name=s.user.name,
                    title=s.title,
                    game=s.game_name,
                    custom_message=partner_msg,
                )
                if msg_id:
                    notified_count += 1
                    streamer = tracked_by_login.get(login)
                    if streamer:
                        await conn.execute(
                            "UPDATE tracked_streamers SET last_live_id=$1, last_message_id=$2 WHERE id=$3",
                            (str(s.id), str(msg_id), streamer["id"]),
                        )

        await ctx.send(await syscmd_msg("checkcopains", "done", count=notified_count))

    @commands.command(name='testpoll')
    async def cmd_testpoll(self, ctx):

        try:
            import app.services.twitch_poll_state as poll_state
            
            poll_state.chat_votes = {1: 0, 2: 0, 3: 0, 4: 0}
            poll_state.current_twitch_poll = {
                "title": "Ceci est un test de Félix !",
                "total_votes": 10,
                "is_prediction": False,
                "choices": [
                    {"title": "Choix A", "votes": 5},
                    {"title": "Choix B", "votes": 5}
                ]
            }

            from app.routes.overlays import trigger_overlay_event
            await trigger_overlay_event({
                "type": "show_twitch_poll",
                "payload": poll_state.current_twitch_poll
            })
            
            from app.services.bot_system_commands_service import msg as syscmd_msg
            await ctx.send(await syscmd_msg("testpoll", "success"))
            
        except Exception as e:
            print(f"❌ Erreur testpoll : {e}")

    @commands.command(name='level')
    async def cmd_level(self, ctx):
        username = ctx.author.name.lower()
        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT points FROM viewers WHERE LOWER(username) = $1", (username,))
                row = await c.fetchone()
        except Exception as e:
            logger.error(f"Erreur cmd_level : {e}")
            return
        
        from app.services.bot_system_commands_service import msg as syscmd_msg
        points = row['points'] if row else 0
        if points <= 0:
            return await ctx.send(await syscmd_msg("level", "new", user=ctx.author.name))

        level = max(1, int((points / 100) ** (1 / 2.2)))
        next_lvl_xp = int(100 * ((level + 1) ** 2.2))
        await ctx.send(await syscmd_msg("level", "level", user=ctx.author.name, level=level, points=points, next_xp=next_lvl_xp))

    @commands.command(name='rang')
    async def cmd_rang(self, ctx):
        username = ctx.author.name.lower()
        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT username, points FROM viewers WHERE points > 0 ORDER BY points DESC, watchtime DESC")
                viewers = await c.fetchall()
        except Exception as e:
            logger.error(f"Erreur cmd_rang : {e}")
            return
        
        from app.services.bot_system_commands_service import msg as syscmd_msg
        if not viewers:
            return await ctx.send(await syscmd_msg("rang", "empty", user=ctx.author.name))
            
        user_idx = -1
        for i, v in enumerate(viewers):
            if v["username"].lower() == username:
                user_idx = i
                break
                
        if user_idx == -1:
            return await ctx.send(await syscmd_msg("rang", "not_ranked", user=ctx.author.name))
            
        rank = user_idx + 1
        start_idx = max(0, user_idx - 2)
        end_idx = min(len(viewers), user_idx + 3)
        
        leaderboard_snippet = []
        for i in range(start_idx, end_idx):
            pos = i + 1
            v_name = viewers[i]["username"]
            v_pts = viewers[i]["points"]
            
            if i == user_idx:
                leaderboard_snippet.append(f"👉 #{pos} {v_name} ({v_pts} pts)")
            else:
                leaderboard_snippet.append(f"#{pos} {v_name} ({v_pts} pts)")
                
        leaderboard_str = " | ".join(leaderboard_snippet)
        await ctx.send(await syscmd_msg("rang", "rank", user=ctx.author.name, rank=rank, leaderboard=leaderboard_str))

    @commands.command(name='screamer')
    async def cmd_screamer(self, ctx):
        from app.services import alerts_service
        from app.services.bot_system_commands_service import msg as syscmd_msg
        ok = await alerts_service.fire_screamer(source="commande", user=ctx.author.name)
        if ok:
            await ctx.send(await syscmd_msg("screamer", "fired", user=ctx.author.name))
        else:
            await ctx.send(await syscmd_msg("screamer", "disabled"))

    @commands.command(name='timer')
    async def cmd_timer(self, ctx, time_str: str = None, *, label: str = "OBJECTIF"):
        from app.services.bot_system_commands_service import msg as syscmd_msg, get_config
        syscmd_cfg = await get_config("timer")
        cmd_label = syscmd_cfg["command_name"] if syscmd_cfg else "timer"
        if not time_str: return await ctx.send(await syscmd_msg("timer", "usage", command=cmd_label))

        session = await self.get_web_session()

        if time_str.lower() in ["stop", "reset", "off", "clear"]:
            payload = { "type": "time_event", "details": { "action": "stop" } }
            try:
                async with session.post(f"{settings.OVERLAY_NODE_URL}/api/trigger", json=payload) as _:
                    pass
                await ctx.send(await syscmd_msg("timer", "stop"))
            except Exception as e:
                logger.error(f"Erreur Stop Timer OBS : {e}")
            return

        try:
            minutes = int(time_str)
            duration_seconds = minutes * 60
        except ValueError:
            return await ctx.send(await syscmd_msg("timer", "invalid", command=cmd_label))

        payload = {
            "type": "time_event",
            "details": { "action": "start", "mode": "timer", "duration": duration_seconds, "label": label.upper() }
        }
        try:
            async with session.post(f"{settings.OVERLAY_NODE_URL}/api/trigger", json=payload) as _:
                pass
            await ctx.send(await syscmd_msg("timer", "start", minutes=minutes, label=label.upper()))
        except Exception as e:
            logger.error(f"Erreur Envoi Timer OBS : {e}")

    @commands.command(name='chrono')
    async def cmd_chrono(self, ctx, *, label: str = "CHRONO"):
        from app.services.bot_system_commands_service import msg as syscmd_msg
        
        session = await self.get_web_session()

        if label and label.lower() in ["stop", "reset", "off", "clear"]:
            payload = { "type": "time_event", "details": { "action": "stop" } }
            try:
                async with session.post(f"{settings.OVERLAY_NODE_URL}/api/trigger", json=payload) as _:
                    pass
                await ctx.send(await syscmd_msg("chrono", "stop"))
            except Exception as e:
                logger.error(f"Erreur Stop Chrono OBS : {e}")
            return

        payload = {
            "type": "time_event",
            "details": { "action": "start", "mode": "chrono", "duration": 0, "label": label.upper() }
        }
        try:
            async with session.post(f"{settings.OVERLAY_NODE_URL}/api/trigger", json=payload) as _:
                pass
            await ctx.send(await syscmd_msg("chrono", "start", label=label.upper()))
        except Exception as e:
            logger.error(f"Erreur Envoi Chrono OBS : {e}")

    @commands.command(name='voteclips')
    async def voteclips_cmd(self, ctx: commands.Context):
        from app.services.bot_system_commands_service import msg as syscmd_msg
        result = await start_clips_poll()          # rôle minimum (et message « denied ») contrôlés en amont
        if "error" in result:
            await ctx.send(await syscmd_msg("voteclips", "error", error=result["error"]))
        else:
            await ctx.send(await syscmd_msg("voteclips", "success"))

    @commands.command(name='addvip')
    async def cmd_addvip(self, ctx, target: str = None, duration_days: int = 0):

        from app.services.bot_system_commands_service import msg as syscmd_msg, get_config
        syscmd_cfg = await get_config("addvip")
        cmd_label = syscmd_cfg["command_name"] if syscmd_cfg else "addvip"
        if not target:
            return await ctx.send(await syscmd_msg("addvip", "usage", command=cmd_label))

        target_clean = target.lower().replace("@", "")

        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT twitch_id FROM viewers WHERE LOWER(username) = $1", (target_clean,))
                viewer = await c.fetchone()

                if not viewer:
                    return await ctx.send(await syscmd_msg("addvip", "not_found", target=target))

                expiry = None
                if duration_days > 0:
                    expiry = (datetime.now() + timedelta(days=duration_days)).isoformat()

                await conn.execute("UPDATE viewers SET is_vip = 1, vip_expiry = $1 WHERE LOWER(username) = $2", (expiry, target_clean))
        except Exception as e:
            logger.error(f"❌ [DB ERROR] Erreur API Twitch !addvip (Base de données) : {e}")
            return

        try:
            headers = {"Client-ID": self._http.client_id, "Authorization": f"Bearer {self.master_token}"}
            url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={self.broadcaster_id}&user_id={viewer['twitch_id']}"
            
            session = await self.get_web_session()
            async with session.post(url, headers=headers) as _:
                pass
        except Exception as e:
            logger.error(f"Erreur API Twitch !addvip (Réseau) : {e}")

        if duration_days > 0:
            await ctx.send(await syscmd_msg("addvip", "success_temp", target=target, days=duration_days))
        else:
            await ctx.send(await syscmd_msg("addvip", "success_permanent", target=target))

    @commands.command(name='vip')
    async def cmd_vip(self, ctx):
        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT is_vip, vip_expiry FROM viewers WHERE twitch_id = $1", (str(ctx.author.id),))
                user = await c.fetchone()
        except Exception as e:
            logger.error(f"❌ [DB ERROR] Erreur cmd_vip : {e}")
            return

        from app.services.bot_system_commands_service import msg as syscmd_msg
        if not user or not user['is_vip']:
            return await ctx.send(await syscmd_msg("vip", "not_vip", user=ctx.author.name))

        if not user['vip_expiry']:
            return await ctx.send(await syscmd_msg("vip", "permanent", user=ctx.author.name))

        try:
            expiry = datetime.fromisoformat(user['vip_expiry'])
            now = datetime.now()

            if expiry < now:
                return await ctx.send(await syscmd_msg("vip", "expired", user=ctx.author.name, date=expiry.strftime('%d/%m/%Y')))

            diff = expiry - now
            days = diff.days
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            time_str = ""
            if days > 0: time_str += f"{days} jours et "
            if hours > 0: time_str += f"{hours}h"
            if minutes > 0 and days == 0: time_str += f"{minutes}m"

            if not time_str: time_str = "quelques secondes"

            await ctx.send(await syscmd_msg("vip", "temp", user=ctx.author.name, time=time_str, date=expiry.strftime('%d/%m/%Y à %H:%M')))
        except:
            await ctx.send(f"@{ctx.author.name}, ton grade VIP est bien actif ! 💎")

    @commands.command(name='permit')
    async def cmd_permit(self, ctx, *, target: str = None):
        from app.services.bot_system_commands_service import msg as syscmd_msg, get_config
        syscmd_cfg = await get_config("permit")
        cmd_label = syscmd_cfg["command_name"] if syscmd_cfg else "permit"
        if not target:
            return await ctx.send(await syscmd_msg("permit", "usage", command=cmd_label))
        target_clean = target.strip().lstrip('@').lower()
        _permitted_users.add(target_clean)
        await ctx.send(await syscmd_msg("permit", "success", target=target_clean))
        async def revoke():
            await asyncio.sleep(60)
            _permitted_users.discard(target_clean)
        asyncio.create_task(revoke())

    @commands.command(name='unpermit')
    async def cmd_unpermit(self, ctx, *, target: str = None):
        from app.services.bot_system_commands_service import msg as syscmd_msg, get_config
        syscmd_cfg = await get_config("unpermit")
        cmd_label = syscmd_cfg["command_name"] if syscmd_cfg else "unpermit"
        if not target:
            return await ctx.send(await syscmd_msg("unpermit", "usage", command=cmd_label))
        target_clean = target.strip().lstrip('@').lower()
        _permitted_users.discard(target_clean)
        await ctx.send(await syscmd_msg("unpermit", "success", target=target_clean))

    @commands.command(name='de')      # nom et alias (dé, dice, roll…) se règlent dans l'admin, ramenés à « de » en amont
    async def cmd_de(self, ctx, max_val: str = "6"):
        import random as _random
        from app.services.bot_system_commands_service import msg as syscmd_msg
        try:
            top = max(2, min(int(max_val), 1000000))
        except (ValueError, TypeError):
            top = 6
        result = _random.randint(1, top)
        await ctx.send(await syscmd_msg("de", "result", user=ctx.author.name, result=result, max=top))

    @commands.command(name='uptime')
    async def cmd_uptime(self, ctx):
        from app.services.bot_system_commands_service import msg as syscmd_msg
        session = await self.get_web_session()
        client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}
        try:
            async with session.get(
                f"https://api.twitch.tv/helix/streams?user_login={self.channel_name}",
                headers=headers
            ) as resp:
                data = await resp.json()
                streams = data.get("data", [])
            if not streams:
                return await ctx.send(await syscmd_msg("uptime", "offline"))
            from datetime import datetime, timezone
            started = datetime.fromisoformat(streams[0]["started_at"].replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - started
            h, rem = divmod(int(delta.total_seconds()), 3600)
            m = rem // 60
            duration = f"{h}h{m:02d}" if h else f"{m} min"
            await ctx.send(await syscmd_msg("uptime", "live", duration=duration))
        except Exception as e:
            logger.error(f"❌ [UPTIME] {e}")

    # Stockage en mémoire des compteurs (persisté en DB pour survivre aux redémarrages)
    _counters: dict = {}

    @commands.command(name='counter')
    async def cmd_counter(self, ctx, *, args: str = ""):
        from app.services.bot_system_commands_service import msg as syscmd_msg
        from app.services.bot_system_commands_service import get_config as _get_cfg, role_allowed
        _cfg = await _get_cfg("counter")
        is_mod = role_allowed((_cfg or {}).get("min_role", "mod"), **self._role_flags(ctx.message))   # peut modifier ?

        args = args.strip()
        # Parsing : "Morts +1", "Morts reset", "Morts", "+1", "reset"
        parts = args.split() if args else []

        # Détermine le label et l'action
        label = "Compteur"
        action = "show"
        delta = 1

        if parts:
            # Cherche si le dernier mot est une action/valeur
            last = parts[-1].lower()
            if last == "reset":
                action = "reset"
                label = " ".join(parts[:-1]) or "Compteur"
            elif last.lstrip("+-").isdigit():
                action = "add"
                delta = int(last)
                label = " ".join(parts[:-1]) or "Compteur"
            else:
                label = " ".join(parts) or "Compteur"
                action = "show"

        # Seuls les mods peuvent modifier
        if action in ("add", "reset") and not is_mod:
            return

        key = label.lower()
        if key not in self._counters:
            self._counters[key] = 0

        if action == "add":
            self._counters[key] += delta
            await ctx.send(await syscmd_msg("counter", "add", label=label, count=self._counters[key], delta=delta))
        elif action == "reset":
            self._counters[key] = 0
            await ctx.send(await syscmd_msg("counter", "reset", label=label))
        else:
            await ctx.send(await syscmd_msg("counter", "show", label=label, count=self._counters[key]))
