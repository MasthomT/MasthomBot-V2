"""Routines périodiques du bot Twitch (watchtime, VIP, rôles, annonces, watchdog…) — mélangées à MasthbotTwitch."""

import random
import os
import time
import logging
from datetime import datetime
from twitchio.ext import routines

from app.core.config import settings
from app.services.credits_service import credits_service
from app.core.database import get_db_connection
from app.core import settings_cache
from app.services.label_service import write_label, lire_fichier_label
from app.services import twitch_common
from app.services.twitch_common import safe_send

logger = logging.getLogger("masthbot.twitch")


class TimersMixin:
    @routines.routine(seconds=60)
    async def watchtime_timer(self):
        if not self.broadcaster_id:
            return

        config = await self.get_db_config()
        if not config.get('personal_last_live_id'):
            return

        exp_to_give = int(config.get('exp_per_watchtime', 5))

        try:
            api_success = False
            session = await self.get_web_session()
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}
            base_url = f"https://api.twitch.tv/helix/chat/chatters?broadcaster_id={self.broadcaster_id}&moderator_id={self.broadcaster_id}&first=1000"

            # Pagination : sans `first` l'API ne renvoie que 100 personnes, donc au-delà (raid,
            # gros event) les suivants ne recevaient ni watchtime ni XP.
            async def _fetch_all_chatters():
                all_chatters, cursor, status = [], None, 200
                while True:
                    page_url = base_url + (f"&after={cursor}" if cursor else "")
                    async with session.get(page_url, headers=headers) as r:
                        status = r.status
                        if status != 200:
                            return None, status
                        page = await r.json()
                    all_chatters.extend(page.get('data', []))
                    cursor = (page.get('pagination') or {}).get('cursor')
                    if not cursor:
                        return all_chatters, status

            chatters_list, chatters_status = await _fetch_all_chatters()
            if chatters_status == 200:
                chatters = chatters_list

                async with get_db_connection() as conn:
                    count = 0
                    for c in chatters:
                        u_name = c['user_name'].lower()
                        t_id = c['user_id']

                        if u_name in [self.nick.lower(), 'nightbot', 'streamelements', 'wizebot']:
                            continue

                        try:
                            await conn.execute("""
                                INSERT INTO viewers (twitch_id, username, watchtime, points) 
                                VALUES ($1, $2, 60, $3)
                                ON CONFLICT(twitch_id) DO UPDATE SET 
                                    watchtime = viewers.watchtime + 60,
                                    points = viewers.points + EXCLUDED.points,
                                    username = EXCLUDED.username
                            """, (t_id, u_name, exp_to_give))
                            
                            await conn.execute("""
                                INSERT INTO viewer_daily_stats (twitch_id, day, watchtime, points_gained)
                                VALUES ($1, CURRENT_DATE, 60, $2)
                                ON CONFLICT(twitch_id, day) DO UPDATE SET
                                    watchtime = viewer_daily_stats.watchtime + 60,
                                    points_gained = viewer_daily_stats.points_gained + EXCLUDED.points_gained
                            """, (t_id, exp_to_give))
                            
                            credits_service.add_watchtime(c['user_name'], 1)
                            count += 1
                        except Exception as e:
                            logger.warning(f"⚠️ Erreur isolée pour {u_name}: {e}")

                    if count > 0:
                        logger.debug(f"💎 Watchtime distribué à {count} personnes.")
                api_success = True

            elif chatters_status in [401, 403]:
                logger.error(f"❌ BLOCAGE TWITCH ({chatters_status}) : Permissions insuffisantes.")

            if not api_success:
                channel = self.get_channel(self.channel_name)
                if channel and hasattr(channel, 'chatters'):
                    async with get_db_connection() as conn:
                        count_fb = 0
                        for chatter in channel.chatters:
                            u_name = chatter.name.lower()
                            if u_name in [self.nick.lower(), 'nightbot', 'streamelements', 'wizebot']: continue

                            c = await conn.execute("SELECT twitch_id FROM viewers WHERE LOWER(username) = $1", (u_name,))
                            row = await c.fetchone()
                            
                            if row:
                                t_id = row['twitch_id']
                                await conn.execute(
                                    "UPDATE viewers SET watchtime = watchtime + 60, points = points + $1 WHERE twitch_id = $2",
                                    (exp_to_give, t_id)
                                )
                                await conn.execute("""
                                    INSERT INTO viewer_daily_stats (twitch_id, day, watchtime, points_gained)
                                    VALUES ($1, CURRENT_DATE, 60, $2)
                                    ON CONFLICT(twitch_id, day) DO UPDATE SET
                                        watchtime = viewer_daily_stats.watchtime + 60,
                                        points_gained = viewer_daily_stats.points_gained + EXCLUDED.points_gained
                                """, (t_id, exp_to_give))
                                credits_service.add_watchtime(chatter.name, 1)
                                count_fb += 1

                        if count_fb > 0:
                            logger.info(f"⚠️ Watchtime (Secours) distribué à {count_fb} personnes.")

        except Exception as e:
            logger.error(f"❌ [DB FATAL] Erreur critique routine Watchtime : {e}")

    @routines.routine(minutes=1)
    async def vip_expiration_timer(self):
        try:
            if not getattr(self, 'broadcaster_id', None):
                users = await self.fetch_users(names=[self.channel_name])
                if users:
                    self.broadcaster_id = users[0].id
                else:
                    return

            now = datetime.now()
            expired_vips = []

            async with get_db_connection() as conn:
                c = await conn.execute("""
                    SELECT twitch_id, username, vip_expiry FROM viewers
                    WHERE is_vip = 1 AND vip_expiry IS NOT NULL
                """)
                vips_to_check = await c.fetchall()

                for v in vips_to_check:
                    twitch_id = v['twitch_id']
                    username = v['username']
                    vip_expiry = v['vip_expiry']

                    try:
                        if isinstance(vip_expiry, datetime):
                            expiry_dt = vip_expiry
                        else:
                            expiry_str = str(vip_expiry).replace("T", " ")
                            if len(expiry_str) == 16:
                                expiry_str += ":00"
                            expiry_dt = datetime.strptime(expiry_str[:19], '%Y-%m-%d %H:%M:%S')

                        if expiry_dt <= now:
                            expired_vips.append({"twitch_id": twitch_id, "username": username})
                    except Exception as e:
                        logger.error(f"❌ Erreur lecture date pour {username} : {e}")

                if expired_vips:
                    headers = {"Client-ID": self._http.client_id, "Authorization": f"Bearer {self.master_token}"}
                    session = await self.get_web_session()

                    for v in expired_vips:
                        await conn.execute(
                            "UPDATE viewers SET is_vip = 0, vip_expiry = NULL WHERE twitch_id = $1",
                            (str(v['twitch_id']),)
                        )
                        
                        try:
                            url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={self.broadcaster_id}&user_id={v['twitch_id']}"
                            async with session.delete(url, headers=headers) as resp:
                                if resp.status in (200, 204):
                                    logger.info(f"✅ VIP Temporaire expiré et retiré sur Twitch pour {v['username']}")
                                else:
                                    logger.error(f"⚠️ Impossible de retirer le VIP de {v['username']} sur Twitch (Erreur {resp.status})")
                        except Exception as e:
                            logger.error(f"❌ Erreur réseau API Twitch pour expiration {v['username']} : {e}")

                    logger.info(f"💾 [DB & TWITCH] Grades de {len(expired_vips)} viewers expirés et retirés avec succès.")
                        
        except Exception as e:
            logger.error(f"💥 CRASH DANS LA ROUTINE VIP : {e}", exc_info=True)

    @routines.routine(hours=1)
    async def sync_roles_timer(self):
        if not self.broadcaster_id: return
        
        try:
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}
            session = await self.get_web_session()
            
            mods = []
            cursor_tw = ""
            while True:
                url = f"https://api.twitch.tv/helix/moderation/moderators?broadcaster_id={self.broadcaster_id}&first=100"
                if cursor_tw: url += f"&after={cursor_tw}"
                async with session.get(url, headers=headers) as r:
                    if r.status != 200: break
                    data = await r.json()
                    mods.extend(data.get("data", []))
                    cursor_tw = data.get("pagination", {}).get("cursor")
                    if not cursor_tw: break
                    
            vips = []
            cursor_tw = ""
            while True:
                url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={self.broadcaster_id}&first=100"
                if cursor_tw: url += f"&after={cursor_tw}"
                async with session.get(url, headers=headers) as r:
                    if r.status != 200: break
                    data = await r.json()
                    vips.extend(data.get("data", []))
                    cursor_tw = data.get("pagination", {}).get("cursor")
                    if not cursor_tw: break

            async with get_db_connection() as conn:
                count_mods, count_vips = 0, 0
                for m in mods:
                    await conn.execute("INSERT INTO viewers (twitch_id, username) VALUES ($1, $2) ON CONFLICT(twitch_id) DO NOTHING", (str(m['user_id']), m['user_login']))
                    await conn.execute("UPDATE viewers SET is_mod = 1 WHERE twitch_id = $1", (str(m['user_id']),))
                    count_mods += 1
                for v in vips:
                    await conn.execute("INSERT INTO viewers (twitch_id, username) VALUES ($1, $2) ON CONFLICT(twitch_id) DO NOTHING", (str(v['user_id']), v['user_login']))
                    await conn.execute("UPDATE viewers SET is_vip = 1 WHERE twitch_id = $1", (str(v['user_id']),))
                    count_vips += 1

            logger.info(f"🔄 [ASPIRATEUR] Synchro Twitch terminée : {count_mods} Modos, {count_vips} VIPs.")

        except Exception as e:
            logger.error(f"❌ [ROUTINE] Erreur dans l'aspirateur Twitch : {e}")

    @routines.routine(minutes=10)
    async def mod_guard_timer(self):
        """Filet de sécurité : un modérateur protégé qui a perdu son statut est remis (en plus de la détection en direct)."""
        if not self.broadcaster_id:
            return
        try:
            from app.services import mod_guard_service
            await mod_guard_service.reconcile("vérification régulière")
        except Exception as e:
            logger.error(f"❌ [ROUTINE] Protection des modérateurs : {e}")

    @routines.routine(minutes=5)
    async def sync_subs_timer(self):
        if not self.broadcaster_id: return

        try:
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {self.master_token}"
            }
            url = f"https://api.twitch.tv/helix/subscriptions?broadcaster_id={self.broadcaster_id}"

            session = await self.get_web_session()
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    total_subs = data.get("total", 0)

                    from app.services.label_service import write_label
                    write_label("nombre_subs.txt", str(total_subs))
                else:
                    logger.warning(f"⚠️ [TWITCH API] Impossible de lire les subs (As-tu l'autorisation 'channel:read:subscriptions' ?) Code: {r.status}")

        except Exception as e:
            logger.error(f"❌ [AUTO-SYNC] Erreur de lecture des abonnés : {e}")

    @routines.routine(minutes=2)
    async def sync_viewers_timer(self):
        if not self.broadcaster_id: return
        # Hors live : rien à compter (stats_service écrit « -- » dans le label sans appeler Twitch).
        if not await settings_cache.is_live(): return

        try:
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {self.master_token}"
            }
            url = f"https://api.twitch.tv/helix/streams?user_id={self.broadcaster_id}"

            session = await self.get_web_session()
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    streams = data.get("data", [])

                    viewers_count = streams[0].get("viewer_count", 0) if streams else 0

                    from app.services.label_service import write_label
                    write_label("viewers.txt", str(viewers_count))
        except Exception as e:
            logger.error(f"❌ [AUTO-SYNC] Erreur de lecture des viewers : {e}")

    @routines.routine(seconds=60)
    async def announcements_timer(self):
        # Hors live : pas d'annonce, et surtout pas d'appel à l'API Twitch chaque minute.
        if not await settings_cache.is_live():
            return
        try:
            try:
                streams = await self.fetch_streams(user_logins=[self.channel_name])
                if not streams:
                    return
            except Exception:
                return

            async with get_db_connection() as conn:
                c1 = await conn.execute("SELECT * FROM announcements WHERE is_enabled = 1 AND trigger_type = 'interval'")
                announcements = await c1.fetchall()
                
                channel = self.get_channel(self.channel_name)
                if not channel or not announcements:
                    return

                now = datetime.now()
                
                min_intervals = []
                for a in announcements:
                    try:
                        val = int(a["interval_minutes"])
                        if val > 0: min_intervals.append(val)
                    except: pass
                
                min_interval = min(min_intervals) if min_intervals else 10
                
                c2 = await conn.execute("SELECT MAX(last_triggered) as max_date FROM announcements WHERE is_enabled = 1 AND trigger_type = 'interval'")
                global_last_row = await c2.fetchone()
                
                if global_last_row and global_last_row["max_date"]:
                    try:
                        global_last = global_last_row["max_date"]
                        if isinstance(global_last, str):
                            global_last = datetime.strptime(global_last, '%Y-%m-%d %H:%M:%S')
                            
                        global_diff = (now - global_last).total_seconds() / 60
                        if global_diff < min_interval:
                            return
                    except: pass

                valid_anns = []
                for ann in announcements:
                    interval = int(ann["interval_minutes"] or 10)
                    last_trig_raw = ann["last_triggered"]
                    
                    if not last_trig_raw:
                        valid_anns.append((ann, 999999))
                    else:
                        try:
                            if isinstance(last_trig_raw, datetime):
                                last_trig = last_trig_raw
                            else:
                                last_trig = datetime.strptime(str(last_trig_raw), '%Y-%m-%d %H:%M:%S')
                                
                            diff = (now - last_trig).total_seconds() / 60
                            if diff >= interval:
                                valid_anns.append((ann, diff - interval))
                        except: pass

                if not valid_anns:
                    return

                valid_anns.sort(key=lambda x: x[1], reverse=True)
                ann_to_send = valid_anns[0][0]
                msg = str(dict(ann_to_send).get("message_template") or "")

                if "{viewers}" in msg:
                    msg = msg.replace("{viewers}", str(len(channel.chatters)) if channel else "0")

                if any(t in msg for t in ["{game}", "{title}", "{uptime}"]):
                    msg = msg.replace("{game}", streams[0].game_name)
                    msg = msg.replace("{title}", streams[0].title)
                    if "{uptime}" in msg:
                        start_time = streams[0].started_at
                        diff = datetime.utcnow() - start_time.replace(tzinfo=None)
                        hours, rem = divmod(int(diff.total_seconds()), 3600)
                        minutes, _ = divmod(rem, 60)
                        msg = msg.replace("{uptime}", f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m")

                if "{viewer_commands}" in msg:
                    from app.services.command_service import list_commands as _list_cmds
                    all_cmds = await _list_cmds(active_only=True)
                    viewer_roles = ("viewer", "everyone", "all", "", None)
                    names = [
                        f"!{c['name']}" for c in all_cmds
                        if c.get("min_role") in viewer_roles
                        and not c.get("vip_owner_twitch_id")
                        and not c.get("hide_from_list")
                    ]
                    random.shuffle(names)
                    msg = msg.replace("{viewer_commands}", ", ".join(names[:6]) if names else "")

                if any(t in msg for t in ["{top5_xp}", "{top5_msg}", "{levelups}", "{last_sub}", "{last_raid}"]):
                    excl_list = ['masthou', 'felixthebigblackcat', 'streamelements', 'wizebot', 'nightbot']
                    
                    if "{top5_xp}" in msg:
                        c_xp = await conn.execute("SELECT username FROM viewers WHERE LOWER(username) != ALL($1) ORDER BY points DESC LIMIT 5", (excl_list,))
                        res_xp = await c_xp.fetchall()
                        msg = msg.replace("{top5_xp}", ", ".join([f"@{r['username']}" for r in res_xp]))
                        
                    if "{top5_msg}" in msg:
                        c_msg = await conn.execute("SELECT username FROM viewers WHERE LOWER(username) != ALL($1) ORDER BY messages DESC LIMIT 5", (excl_list,))
                        res_msg = await c_msg.fetchall()
                        msg = msg.replace("{top5_msg}", ", ".join([f"@{r['username']}" for r in res_msg]))

                    if "{last_sub}" in msg:
                        c_sub = await conn.execute("SELECT username FROM stream_events WHERE event_type = 'sub' ORDER BY timestamp DESC LIMIT 1")
                        ls = await c_sub.fetchone()
                        msg = msg.replace("{last_sub}", ls['username'] if ls else "Personne :(")

                    if "{levelups}" in msg:
                        c_lvl = await conn.execute("SELECT twitch_id, username, points FROM viewers WHERE points > 0")
                        v_db = await c_lvl.fetchall()
                        leveled = []
                        for v in v_db:
                            lvl = max(1, int((v['points'] / 100) ** (1 / 2.2)))
                            tid = str(v['twitch_id'])
                            if tid in self.known_levels and lvl > self.known_levels[tid]:
                                leveled.append(f"@{v['username']} (Lvl {lvl})")
                            self.known_levels[tid] = lvl
                        msg = msg.replace("{levelups}", ", ".join(leveled[:6]) if leveled else "Pas de level up récent !")

                # 1. On cherche le nom de l'annonce peu importe la colonne
                nom_annonce = ann_to_send.get("label") or ann_to_send.get("title") or ann_to_send.get("name", "Annonce sans titre")
                
                # 2. Si le message est totalement vide, on bloque l'envoi et on analyse !
                if not msg or not msg.strip():
                    logger.error(f"❌ ÉCHEC : Le texte de '{nom_annonce}' est vide ! Twitch refuse de l'envoyer.")
                    logger.error(f"🔍 Voici les VRAIES colonnes de ta base de données : {list(ann_to_send.keys())}")
                    # Message vide = problème de config, pas de retry utile : on marque comme traité.
                    await conn.execute("UPDATE announcements SET last_triggered = $1 WHERE id = $2", (now, ann_to_send['id']))
                else:
                    # 3. L'envoi officiel sur Twitch
                    logger.info(f"📢 [ANNONCE] Envoi sur le chat : '{nom_annonce}'")
                    sent = await safe_send(channel, msg) if channel else False

                    # 4. On ne marque comme traité QUE si l'envoi a réussi : un échec transitoire
                    # (ex: reconnexion IRC) déclenche une nouvelle tentative au prochain cycle
                    # plutôt que de perdre l'annonce jusqu'au prochain intervalle complet.
                    if sent:
                        await conn.execute("UPDATE announcements SET last_triggered = $1 WHERE id = $2", (now, ann_to_send['id']))
                    else:
                        logger.warning(f"⚠️ [ANNONCE] '{nom_annonce}' non envoyée, nouvelle tentative au prochain cycle.")

        except Exception as e:
            if "closing transport" not in str(e):
                logger.error(f"❌ [ROUTINE ERROR] Announcements Timer : {e}")

    @routines.routine(seconds=90)
    async def special_announcements_timer(self):
        """Gère les annonces 'Début de Stream' (une fois par session live) et
        'Une seule fois' (une fois pour toujours), qui étaient configurables dans
        le panel admin mais jamais lues par aucune routine jusqu'ici."""
        if not await settings_cache.is_live():
            return
        try:
            streams = await self.fetch_streams(user_logins=[self.channel_name])
            if not streams:
                return

            channel = self.get_channel(self.channel_name)
            if not channel:
                return

            stream_started_at = streams[0].started_at.replace(tzinfo=None)
            now = datetime.now()

            async with get_db_connection() as conn:
                c = await conn.execute(
                    "SELECT * FROM announcements WHERE is_enabled = 1 AND trigger_type IN ('stream_start', 'once')"
                )
                anns = await c.fetchall()

                for ann in anns:
                    ann = dict(ann)
                    last_trig_raw = ann.get("last_triggered")
                    last_trig = None
                    if last_trig_raw:
                        last_trig = last_trig_raw if isinstance(last_trig_raw, datetime) else datetime.strptime(str(last_trig_raw), '%Y-%m-%d %H:%M:%S')

                    should_send = False
                    if ann["trigger_type"] == "once":
                        should_send = last_trig is None
                    elif ann["trigger_type"] == "stream_start":
                        should_send = last_trig is None or last_trig < stream_started_at

                    if not should_send:
                        continue

                    msg = str(ann.get("message_template") or "")
                    if not msg.strip():
                        continue

                    msg = msg.replace("{game}", streams[0].game_name).replace("{title}", streams[0].title)
                    sent = await safe_send(channel, msg)
                    if not sent:
                        logger.warning(f"⚠️ [ANNONCE {ann['trigger_type'].upper()}] '{ann.get('label', 'Sans titre')}' non envoyée, nouvelle tentative au prochain cycle.")
                        continue

                    logger.info(f"📢 [ANNONCE {ann['trigger_type'].upper()}] Envoi : '{ann.get('label', 'Sans titre')}'")

                    if ann["trigger_type"] == "once":
                        await conn.execute("UPDATE announcements SET last_triggered = $1, is_enabled = 0 WHERE id = $2", (now, ann["id"]))
                    else:
                        await conn.execute("UPDATE announcements SET last_triggered = $1 WHERE id = $2", (now, ann["id"]))
        except Exception as e:
            if "closing transport" not in str(e):
                logger.error(f"❌ [ROUTINE ERROR] Special Announcements Timer : {e}")

    @routines.routine(minutes=5)
    async def watchdog_timer(self):
        routines_to_check = {
            "Watchtime": self.watchtime_timer,
            "Annonces": self.announcements_timer,
            "Annonces Spéciales": self.special_announcements_timer,
            "Aspirateur de Rôles": self.sync_roles_timer,
            "Protection des modos": self.mod_guard_timer,
            "Compteur Subs": self.sync_subs_timer,
            "Compteur Viewers": self.sync_viewers_timer,
            "Expiration VIP": self.vip_expiration_timer,
            "Détecteur Followers": self.followers_detector_timer
        }

        for name, routine in routines_to_check.items():
            try:
                if routine._task is None:
                    logger.info(f"▶️ [WATCHDOG] Démarrage initial de la routine '{name}'...")
                    routine.start()
                elif routine._task.done():
                    logger.warning(f"⚠️ [WATCHDOG] La routine '{name}' a crashé ! Relance de force...")
                    routine.restart()
            except Exception as e:
                logger.error(f"❌ [WATCHDOG] Erreur inattendue lors de la vérification de '{name}' : {e}")

        try:
            session = await self.get_web_session()
            async with session.get(f"{settings.OVERLAY_NODE_URL}/", timeout=2) as resp:
                pass
        except Exception:
            logger.error("🚨 [WATCHDOG FATAL] Impossible de contacter Node.js (Port 3005) ! L'overlay est probablement éteint ou planté.")

        # Filet IRC : déclenche uniquement si le bot est censé être connecté (is_ready_flag)
        # et qu'aucun message n'a été reçu depuis 2h. Le seuil est élevé car le chat peut
        # être parfaitement silencieux pendant de longues périodes (nuit, hors stream).
        # Les TCP keepalives OS détectent les vraies coupures réseau en ~60s.
        if getattr(self, 'is_ready_flag', False):
            # Hors live, un chat muet est NORMAL (nuit, jours sans stream) : sans cette garde le
            # watchdog tuait le bot toutes les 2 h en continu (104 redémarrages en 10 jours).
            # On remet donc le compteur à zéro tant que la chaîne n'est pas en direct ; l'horloge
            # des 2 h ne démarre qu'à l'ouverture du live. Les vraies coupures réseau restent
            # détectées par les keepalives TCP et par le filet "envois bloqués" ci-dessous.
            try:
                is_live_now = bool((await self.get_db_config()).get('personal_last_live_id'))
            except Exception:
                is_live_now = True  # dans le doute on garde la protection active
            if not is_live_now:
                self._last_irc_at = time.time()

            irc_silence = time.time() - getattr(self, '_last_irc_at', time.time())
            if irc_silence > 7200:
                logger.error(f"🚨 [IRC WATCHDOG] Aucun message IRC depuis {int(irc_silence//60)}min — reconnexion forcée.")
                import signal as _signal
                os.kill(os.getpid(), _signal.SIGTERM)

            # Filet ENVOI : contrairement à la réception, l'écriture peut rester bloquée
            # ("closing transport" en continu) alors que le bot reçoit toujours des messages
            # — le filet ci-dessus ne voit donc rien passer. Constaté le 07/07/2026 : les
            # annonces échouaient en boucle pendant 10+ minutes sans jamais se rétablir seules.
            # Seuil court (3 min) car un vrai cycle de reconnexion Twitch est bien plus rapide.
            if twitch_common._send_failure_since is not None and (time.time() - twitch_common._send_failure_since) > 180:
                logger.error(f"🚨 [IRC WATCHDOG] Envois bloqués depuis {int(time.time() - twitch_common._send_failure_since)}s — reconnexion forcée.")
                import signal as _signal
                os.kill(os.getpid(), _signal.SIGTERM)

    @routines.routine(seconds=60)
    async def followers_detector_timer(self):
        """Filet de sécurité des follows : EventSub (channel.follow) met déjà à jour le label,
        l'alerte et le générique en direct. Ce relevé ne sert qu'à rattraper un follow manqué
        si la connexion EventSub tombe : 1 fois par minute pendant le live suffit (avant :
        toutes les 3 s, 24 h/24, soit ~29 000 appels à l'API Twitch par jour)."""
        if not self.broadcaster_id: return
        if not await settings_cache.is_live(): return

        try:
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {self.master_token}"
            }
            # On interroge Twitch pour voir le tout dernier follower
            url = f"https://api.twitch.tv/helix/channels/followers?broadcaster_id={self.broadcaster_id}&first=1"

            session = await self.get_web_session()
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("data"):
                        latest_follower = data["data"][0]["user_name"]
                        
                        # On lit le dernier enregistré
                        current_follower = lire_fichier_label("dernier_follow.txt")
                        
                        # Si c'est un NOUVEAU follower (Réaction à la seconde près !)
                        if current_follower.lower() != latest_follower.lower():
                            write_label("dernier_follow.txt", latest_follower)
                            credits_service.log_event("followers", latest_follower, "Bienvenue !")
                            logger.info(f"💙 Nouveau Follower instantané : {latest_follower}")
        except Exception as e:
            logger.error(f"❌ [DETECTOR] Erreur Follow : {e}")
