import sqlite3
import aiohttp
import re
import logging
from twitchio.ext import commands
from app.services.notification_service import notification_service

logger = logging.getLogger("masthbot.plugins.admin")
DB_PATH = "bot_database.db"

class AdminToolsPlugin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='so')
    async def shoutout_command(self, ctx: commands.Context, *, content: str = None):
        """Lance l'overlay de SO pour un streameur"""
        is_authorized = ctx.author.is_mod or ctx.author.is_broadcaster or ctx.author.name.lower() == "felixthebigblackcat"
        if not is_authorized: return
        if not content: return await ctx.send("Miaou ! Pseudo ou lien requis : !so masthom_")

        content = content.replace("!so", "").strip()
        link_match = re.search(r"https?://\S*twitch\.tv\S+", content)
        
        target_name = None
        slug_for_node = None

        if link_match:
            url = link_match.group(0)
            slug_for_node = url
            if "twitch.tv/" in url:
                parts = url.split("twitch.tv/")[-1].split("/")
                if parts[0] == "clip" or parts[0] == "":
                    target_name = "ce streameur"
                else:
                    target_name = parts[0].split("?")[0]
            await ctx.send(f"On regarde un clip de @{target_name} ! 🎬")
        else:
            target_name = content.split(" ")[0].replace("@", "").strip()
            headers = {"Client-ID": self.bot._http.client_id, "Authorization": f"Bearer {self.bot.master_token}"}
            
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.get(f"https://api.twitch.tv/helix/users?login={target_name}", headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("data"):
                                streamer = data["data"][0]
                                s_id, s_display = streamer["id"], streamer["display_name"]
                                async with session.get(f"https://api.twitch.tv/helix/channels?broadcaster_id={s_id}", headers=headers) as c_resp:
                                    last_game = "un jeu inconnu"
                                    if c_resp.status == 200:
                                        c_data = await c_resp.json()
                                        last_game = c_data["data"][0].get("game_name", "Just Chatting")
                                await ctx.send(f"Rendez visite à @{s_display} qui jouait la dernière fois à {last_game} ! https://twitch.tv/{target_name} 💜")
                            else:
                                await ctx.send(f"Foncez voir @{target_name} ! https://twitch.tv/{target_name}")
                except:
                    await ctx.send(f"Allez donner de la force à @{target_name} ! https://twitch.tv/{target_name}")

        timeout_node = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout_node) as session:
            try:
                await session.post("http://127.0.0.1:3005/api/shoutout", json={"target": target_name, "slug": slug_for_node})
            except: pass

    @commands.command(name='replay')
    async def cmd_replay(self, ctx: commands.Context, *, content: str = None):
        """Lance le replay sur l'overlay OBS et annonce dans le chat"""
        if not (ctx.author.is_mod or ctx.author.is_broadcaster or ctx.author.name.lower() == 'felixthebigblackcat'): return

        slug, query = None, None
        extracted_slug = None

        if content:
            content = content.strip()
            if "twitch.tv" in content: 
                slug = content
                # On extrait l'ID exact du clip pour interroger l'API Twitch
                extracted_slug = content.split('/')[-1].split('?')[0]
            else: 
                query = content

        timeout = aiohttp.ClientTimeout(total=5)
        
        # 1. On prévient la régie Node.js de lancer la vidéo sur OBS
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                payload = {"slug": slug, "query": query}
                await session.post("http://127.0.0.1:3005/api/replay", json=payload)
            except Exception as e:
                logger.error(f"❌ [REPLAY ERROR] : {e}")

        # 2. On récupère les infos du clip via l'API Twitch pour le t'chat
        headers = {
            "Client-ID": self.bot._http.client_id,
            "Authorization": f"Bearer {self.bot.master_token}"
        }
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                clip_data = None
                if extracted_slug:
                    # Si c'est un lien précis, on cherche son ID
                    async with session.get(f"https://api.twitch.tv/helix/clips?id={extracted_slug}", headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("data"): clip_data = data["data"][0]
                elif query:
                    # On fouille dans les 100 derniers clips de la chaîne pour trouver le titre exact
                    async with session.get(f"https://api.twitch.tv/helix/clips?broadcaster_id={self.bot.broadcaster_id}&first=100", headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            clips = data.get("data", [])
                            for c in clips:
                                if query.lower() in c.get("title", "").lower():
                                    clip_data = c
                                    break
                elif not query:
                    # S'il n'y a pas de lien (commande !replay simple), on récupère le DERNIER clip de ta chaîne
                    async with session.get(f"https://api.twitch.tv/helix/clips?broadcaster_id={self.bot.broadcaster_id}&first=1", headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("data"): clip_data = data["data"][0]
                
                # 3. L'annonce de Félix dans le chat !
                if clip_data:
                    titre = clip_data.get("title", "un clip incroyable")
                    clippeur = clip_data.get("creator_name", "un viewer")
                    await ctx.send(f"🎬 On regarde le clip \"{titre}\" de @{clippeur} !")
                elif query:
                    # Au cas où Twitch ne trouve pas le clip dans les 100 derniers
                    await ctx.send(f"🎬 Lancement du clip recherché : {query} !")
                else:
                    await ctx.send("🎬 Lancement du dernier clip en date !")
                    
            except Exception as e:
                logger.error(f"❌ [TWITCH CLIP ERROR] : {e}")

    @commands.command(name='renotif')
    async def cmd_renotif(self, ctx: commands.Context):
        """Renvoie l'alerte sur Discord avec la bonne catégorie"""
        if not ctx.author.is_mod and not ctx.author.is_broadcaster: return
        config = self.bot.get_db_config()
        channel_id = config.get('notif_live_channel_id')
        if not channel_id: return await ctx.send("❌ Aucun salon Discord n'est configuré.")

        streams = await self.bot.fetch_streams(user_logins=[self.bot.channel_name])
        if streams:
            s = streams[0]
            await notification_service.send_discord_live_notification(
                channel_id=channel_id,
                channel_name=self.bot.channel_name,
                title=s.title,
                game=s.game_name,
                custom_message=config.get('discord_notify_message')
            )
            await ctx.send(f"✅ Notification renvoyée sur Discord avec la catégorie : {s.game_name} !")
        else:
            await ctx.send("⏳ Twitch ne te voit pas en live. Attends 1 minute et réessaie !")

    @commands.command(name='checkcopains')
    async def cmd_checkcopains(self, ctx: commands.Context):
        """Notifie si des partenaires sont en live"""
        if not ctx.author.is_mod and not ctx.author.is_broadcaster: return
        config = self.bot.get_db_config()
        channel_id = config.get('streamers_channel_id')
        if not channel_id: return await ctx.send("❌ Aucun salon Discord configuré.")

        conn = sqlite3.connect(DB_PATH, timeout=20.0)
        conn.row_factory = sqlite3.Row
        tracked = conn.execute("SELECT * FROM tracked_streamers WHERE is_active=1").fetchall()
        conn.close()

        if not tracked: return await ctx.send("⚠️ Aucun partenaire surveillé.")

        logins = [s["login"] for s in tracked]
        await ctx.send(f"🔍 Scan des {len(logins)} copains...")
        
        streams = await self.bot.fetch_streams(user_logins=logins)
        if not streams: return await ctx.send("💤 Aucun copain n'est en ligne.")

        notified_count = 0
        for s in streams:
            partner_msg = f"**{s.user.name}** est en live sur **{{CATEGORIE}}**, foncez lui donner de la force !"
            await notification_service.send_discord_live_notification(
                channel_id=channel_id,
                channel_name=s.user.name,
                title=s.title,
                game=s.game_name,
                custom_message=partner_msg
            )
            notified_count += 1
            
        await ctx.send(f"✅ {notified_count} alertes envoyées !")

    @commands.command(name='timer')
    async def cmd_timer(self, ctx: commands.Context, time_str: str = None, *, label: str = "OBJECTIF"):
        """Lance un compte à rebours sur l'overlay"""
        if not ctx.author.is_mod and not ctx.author.is_broadcaster: return
        if not time_str: return await ctx.send("⏱️ Usage : !timer <minutes> [Nom du timer]")

        if time_str.lower() in ["stop", "reset", "off", "clear"]:
            payload = { "type": "time_event", "details": { "action": "stop" } }
            timeout = aiohttp.ClientTimeout(total=3)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    await session.post("http://127.0.0.1:3005/api/trigger", json=payload)
                    await ctx.send("🛑 Timer effacé de l'écran !")
                except Exception as e:
                    logger.error(f"Erreur Stop Timer OBS : {e}")
            return

        try:
            minutes = int(time_str)
            duration_seconds = minutes * 60
        except ValueError:
            return await ctx.send("❌ La durée doit être un chiffre exact en minutes (ex: !timer 5)")

        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                "type": "time_event",
                "details": { "action": "start", "mode": "timer", "duration": duration_seconds, "label": label.upper() }
            }
            try:
                await session.post("http://127.0.0.1:3005/api/trigger", json=payload)
                await ctx.send(f"⏱️ Timer de {minutes} minute(s) lancé à l'écran : {label.upper()}")
            except Exception as e:
                logger.error(f"Erreur Envoi Timer OBS : {e}")

    @commands.command(name='chrono')
    async def cmd_chrono(self, ctx: commands.Context, *, label: str = "CHRONO"):
        """Lance un chronomètre sur l'overlay"""
        if not ctx.author.is_mod and not ctx.author.is_broadcaster: return

        if label and label.lower() in ["stop", "reset", "off", "clear"]:
            payload = { "type": "time_event", "details": { "action": "stop" } }
            timeout = aiohttp.ClientTimeout(total=3)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    await session.post("http://127.0.0.1:3005/api/trigger", json=payload)
                    await ctx.send("🛑 Chrono effacé de l'écran !")
                except Exception as e:
                    logger.error(f"Erreur Stop Chrono OBS : {e}")
            return

        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                "type": "time_event",
                "details": { "action": "start", "mode": "chrono", "duration": 0, "label": label.upper() }
            }
            try:
                await session.post("http://127.0.0.1:3005/api/trigger", json=payload)
                await ctx.send(f"⏱️ Chronomètre lancé à l'écran : {label.upper()}")
            except Exception as e:
                logger.error(f"Erreur Envoi Chrono OBS : {e}")

def prepare(bot: commands.Bot):
    # C'EST CETTE LIGNE QUI PLANTAIT CHEZ TOI ! Elle charge bien AdminToolsPlugin maintenant.
    bot.add_cog(AdminToolsPlugin(bot))
