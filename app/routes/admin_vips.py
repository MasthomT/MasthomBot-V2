import logging
import aiohttp
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# --- IMPORT CORE POSTGRESQL & CONFIG ---
from app.core.database import get_db_connection
from app.core.config import settings
from app.core.security import require_admin

logger = logging.getLogger("masthbot.vips")
router = APIRouter(prefix="/admin", tags=["vips_team"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="app/templates")

async def init_team_columns():
    """Vérifie et ajoute les colonnes d'équipe manquantes proprement sous PostgreSQL."""
    async with get_db_connection() as conn:
        try:
            await conn.execute("ALTER TABLE viewers ADD COLUMN IF NOT EXISTS is_mod INTEGER DEFAULT 0")
            await conn.execute("ALTER TABLE viewers ADD COLUMN IF NOT EXISTS is_artist INTEGER DEFAULT 0")
        except Exception as e:
            logger.warning(f"⚠️ Info init_team_columns : {e}")

# ==========================================
# 📊 ROUTE PRINCIPALE
# ==========================================
@router.get("/vips", response_class=HTMLResponse)
async def admin_vips_page(request: Request):
    await init_team_columns()
    async with get_db_connection() as conn:
        # On affiche tout le monde en lecture seule depuis PostgreSQL
        c_vips = await conn.execute("SELECT twitch_id, username, is_vip, vip_expiry FROM viewers WHERE is_vip = 1 ORDER BY username ASC")
        vips = await c_vips.fetchall()
        
        c_mods = await conn.execute("SELECT twitch_id, username FROM viewers WHERE is_mod = 1 ORDER BY username ASC")
        mods = await c_mods.fetchall()
        
        c_artists = await conn.execute("SELECT twitch_id, username FROM viewers WHERE is_artist = 1 ORDER BY username ASC")
        artists = await c_artists.fetchall()
        
    return templates.TemplateResponse(
        request=request, 
        name="admin/admin_vips.html", 
        context={"request": request, "vips": vips, "mods": mods, "artists": artists}
    )

# ==========================================
# 🔄 L'ASPIRATEUR AUTOMATIQUE (VIP + MODOS)
# ==========================================
@router.post("/vips/sync")
async def sync_vips_from_twitch():
    await init_team_columns()
    try:
        token = settings.TWITCH_OAUTH_TOKEN.replace("oauth:", "").strip()
        channel_name = settings.TWITCH_CHANNEL.replace("#", "").lower().strip()
        if not token: return RedirectResponse(url="/admin/vips?error=sync_failed", status_code=303)
            
        async with aiohttp.ClientSession() as session:
            # 1. Validation Twitch
            async with session.get("https://id.twitch.tv/oauth2/validate", headers={"Authorization": f"OAuth {token}"}) as r:
                if r.status != 200: return RedirectResponse(url="/admin/vips?error=sync_failed", status_code=303)
                client_id = (await r.json())['client_id']
            
            headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
            async with session.get(f"https://api.twitch.tv/helix/users?login={channel_name}", headers=headers) as r:
                broadcaster_id = (await r.json())['data'][0]['id']
                
            # 2. Aspiration des VIPS
            vips = []
            cursor = ""
            while True:
                url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={broadcaster_id}&first=100"
                if cursor: url += f"&after={cursor}"
                async with session.get(url, headers=headers) as r:
                    if r.status != 200: break
                    data = await r.json()
                    vips.extend(data.get("data", []))
                    cursor = data.get("pagination", {}).get("cursor")
                    if not cursor: break
                        
            # 3. Aspiration des MODÉRATEURS
            mods = []
            cursor = ""
            while True:
                url = f"https://api.twitch.tv/helix/moderation/moderators?broadcaster_id={broadcaster_id}&first=100"
                if cursor: url += f"&after={cursor}"
                async with session.get(url, headers=headers) as r:
                    if r.status != 200: break
                    data = await r.json()
                    mods.extend(data.get("data", []))
                    cursor = data.get("pagination", {}).get("cursor")
                    if not cursor: break

            async with get_db_connection() as conn:
                # 4. Enregistrement en base de données PostgreSQL
                # On met tout le monde à 0 pour éviter les anciens rôles, puis on recoche
                await conn.execute("UPDATE viewers SET is_vip = 0, is_mod = 0 WHERE is_vip = 1 OR is_mod = 1")
                
                count_vips = 0
                for v in vips:
                    t_id = v['user_id']
                    u_name = v['user_login']

                    await conn.execute("INSERT INTO viewers (twitch_id, username) VALUES ($1, $2) ON CONFLICT(twitch_id) DO NOTHING", (str(t_id), u_name))
                    await conn.execute("UPDATE viewers SET is_vip = 1 WHERE twitch_id = $1", (str(t_id),))
                    count_vips += 1
                
                count_mods = 0
                for m in mods:
                    t_id = m['user_id']
                    u_name = m['user_login']
                    await conn.execute("INSERT INTO viewers (twitch_id, username) VALUES ($1, $2) ON CONFLICT(twitch_id) DO NOTHING", (str(t_id), u_name))
                    await conn.execute("UPDATE viewers SET is_mod = 1 WHERE twitch_id = $1", (str(t_id),))
                    count_mods += 1
                
            logger.info(f"🔄 [SYNCHRO] {count_vips} VIPs et {count_mods} Modérateurs aspirés depuis Twitch !")
            return RedirectResponse(url="/admin/vips?success=synced", status_code=303)
    except Exception as e:
        logger.error(f"❌ Erreur de synchro VIP/Mods : {e}")
        return RedirectResponse(url="/admin/vips?error=sync_failed", status_code=303)

@router.post("/vips/add")
async def add_vip(request: Request, username: str = Form(...), duration_days: int = Form(...), exact_date: str = Form(None)):
    logger.warning(f"🚨 TENTATIVE D'AJOUT VIP WEB POUR : {username}")
    async with get_db_connection() as conn:
        clean_username = username.lower().strip().replace("@", "")
        expiry = None
        
        cursor = await conn.execute("SELECT twitch_id FROM viewers WHERE LOWER(username) = $1", (clean_username,))
        viewer = await cursor.fetchone()
        if not viewer:
            logger.warning("❌ Utilisateur introuvable dans la base.")
            return RedirectResponse(url="/admin/vips?error=not_found", status_code=303)
        twitch_id = viewer["twitch_id"]

        if duration_days == -1:
            if not exact_date: return RedirectResponse(url="/admin/vips?error=missing_date", status_code=303)
            expiry = exact_date.replace("T", " ")
            if len(expiry) == 16: expiry += ":00"
        elif duration_days > 0:
            expiry = (datetime.now() + timedelta(days=duration_days)).isoformat()

        await conn.execute("UPDATE viewers SET is_vip = 1, vip_expiry = $1 WHERE twitch_id = $2", (expiry, twitch_id))
        logger.warning("✅ Base de données mise à jour.")

        # --- Appel à l'API Twitch via le moteur réseau du bot ---
        if hasattr(request.app.state, 'bot'):
            bot = request.app.state.bot
            try:
                headers = {"Client-ID": bot._http.client_id, "Authorization": f"Bearer {bot.master_token}"}
                url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={bot.broadcaster_id}&user_id={twitch_id}"
                
                session = await bot.get_web_session()
                async with session.post(url, headers=headers) as resp:
                    if resp.status in (200, 204):
                        logger.warning("✅ Badge Twitch accordé avec succès !")
                    else:
                        logger.error(f"⚠️ Twitch a répondu avec le code {resp.status}")
            except Exception as e:
                logger.error(f"❌ Erreur réseau API Twitch (Add VIP) : {e}")
        else:
            logger.error("❌ ERREUR FATALE : app.state.bot manquant !")

        return RedirectResponse(url="/admin/vips?success=added", status_code=303)

@router.post("/vips/extend/{twitch_id}")
async def extend_vip(twitch_id: str, extra_days: int = Form(...)):
    """Prolonge un VIP temporaire sans avoir à le révoquer puis le réajouter."""
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT vip_expiry FROM viewers WHERE twitch_id = $1", (twitch_id,))
        row = await cursor.fetchone()
        if not row:
            return RedirectResponse(url="/admin/vips?error=not_found", status_code=303)

        current_expiry = row["vip_expiry"]
        base = datetime.now()
        if current_expiry:
            try:
                parsed = current_expiry if isinstance(current_expiry, datetime) else datetime.fromisoformat(str(current_expiry).replace("T", " "))
                if parsed > base:
                    base = parsed
            except ValueError:
                pass

        new_expiry = (base + timedelta(days=extra_days)).isoformat()
        await conn.execute("UPDATE viewers SET is_vip = 1, vip_expiry = $1 WHERE twitch_id = $2", (new_expiry, twitch_id))
        logger.info(f"⏳ [VIP] Prolongation de {extra_days}j pour twitch_id={twitch_id}, nouvelle expiration : {new_expiry}")

    return RedirectResponse(url="/admin/vips?success=extended", status_code=303)


@router.post("/vips/revoke/{twitch_id}")
async def revoke_vip(request: Request, twitch_id: str):
    logger.warning(f"🚨 TENTATIVE DE RETRAIT VIP WEB POUR L'ID : {twitch_id}")
    async with get_db_connection() as conn:
        await conn.execute("UPDATE viewers SET is_vip = 0, vip_expiry = NULL WHERE twitch_id = $1", (str(twitch_id),))
        logger.warning("✅ Base de données mise à jour (Retrait).")

        # --- Appel à l'API Twitch via le moteur réseau du bot ---
        if hasattr(request.app.state, 'bot'):
            bot = request.app.state.bot
            try:
                headers = {"Client-ID": bot._http.client_id, "Authorization": f"Bearer {bot.master_token}"}
                url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={bot.broadcaster_id}&user_id={twitch_id}"
                
                session = await bot.get_web_session()
                async with session.delete(url, headers=headers) as resp:
                    if resp.status in (200, 204):
                        logger.warning("✅ Badge Twitch retiré avec succès !")
                    else:
                        logger.error(f"⚠️ Twitch a répondu avec le code {resp.status}")
            except Exception as e:
                logger.error(f"❌ Erreur réseau API Twitch (Revoke VIP) : {e}")

        return RedirectResponse(url="/admin/vips?success=revoked", status_code=303)
