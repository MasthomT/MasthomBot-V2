import aiohttp
import logging
from twitchio.ext import commands
from app.repositories import viewer_repo
from app.core.database import get_db_connection
from app.core.config import settings

logger = logging.getLogger("masthbot.plugins.viewers")

class ViewerToolsPlugin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='sondage')
    async def cmd_sondage(self, ctx: commands.Context):
        """Affiche les résultats du sondage en cours"""
        try:
            async with get_db_connection() as conn:
                c1 = await conn.execute("SELECT * FROM polls WHERE is_active=1 ORDER BY id DESC LIMIT 1")
                poll = await c1.fetchone()
                
                if not poll:
                    return await ctx.send("🐾 Aucun sondage en cours. Check ton profil sur https://fel-x.vercel.app !")

                c2 = await conn.execute("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id=$1 GROUP BY option_index", (poll['id'],))
                votes = await c2.fetchall()
                
            results = {1: 0, 2: 0, 3: 0, 4: 0}
            total = 0
            for v in votes:
                results[v['option_index']] = v['count']
                total += v['count']

            # On force l'affichage de l'overlay sur OBS
            timeout = aiohttp.ClientTimeout(total=3)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {"type": "show_poll"}
                try:
                    await session.post(f"{settings.OVERLAY_NODE_URL}/api/trigger", json=payload)
                except Exception:
                    pass

            msg = f"📊 SONDAGE : {poll['question']} — "
            options_text = []
            for i in range(1, 5):
                opt_name = poll[f'option{i}']
                if opt_name:
                    count = results[i]
                    pct = round((count / total) * 100) if total > 0 else 0
                    options_text.append(f"{i}. {opt_name} ({pct}%)")

            msg += " | ".join(options_text)
            msg += f" — 🗳️ Vote avec !choix 1, 2... ({total} votes)"
            await ctx.send(msg)

        except Exception as e:
            logger.error(f"Erreur cmd_sondage: {e}")

    @commands.command(name='level')
    async def cmd_level(self, ctx: commands.Context):
        """Affiche le niveau du viewer"""
        row = await viewer_repo.get_viewer_by_name(ctx.author.name.lower())
        if row:
            p = row.points
            lvl = max(1, int((p / 100) ** (1 / 2.2)))
            next_p = int(100 * ((lvl + 1) ** 2.2))
            await ctx.send(f"@{ctx.author.name}, tu es Niveau {lvl} ({p} EXP). Prochain niveau à {next_p} ! 🌟")
        else:
            await ctx.send(f"@{ctx.author.name}, tu n'as pas encore d'EXP pour avoir un niveau ! 🐾")

    @commands.command(name='rang')
    async def cmd_rang(self, ctx: commands.Context):
        """Affiche la position du viewer dans le classement global"""
        username = ctx.author.name.lower()
        
        if username in ['masthom_', 'felixthebigblackcat']:
            return await ctx.send(f"@{ctx.author.name}, tu es hors catégorie, tu es au-dessus de tout ça ! 👑")
            
        try:
            async with get_db_connection() as conn:
                exclusion_list = "('masthom_', 'felixthebigblackcat', 'streamelements', 'wizebot', 'nightbot')"
                c = await conn.execute(f"SELECT username, points FROM viewers WHERE points > 0 AND LOWER(username) NOT IN {exclusion_list} ORDER BY points DESC, watchtime DESC")
                viewers = await c.fetchall()
        except Exception as e:
            logger.error(f"Erreur BDD cmd_rang: {e}")
            return
        
        if not viewers:
            return await ctx.send(f"@{ctx.author.name}, le classement est vide pour le moment !")
            
        user_idx = -1
        for i, v in enumerate(viewers):
            if v["username"].lower() == username:
                user_idx = i
                break
                
        if user_idx == -1:
            return await ctx.send(f"@{ctx.author.name}, tu n'as pas encore d'EXP pour être classé ! 🐾")
            
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
                
        msg = " | ".join(leaderboard_snippet)
        await ctx.send(f"🏆 Classement (Rang #{rank}) : {msg}")

def prepare(bot: commands.Bot):
    bot.add_cog(ViewerToolsPlugin(bot))
