import asyncio

try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
import subprocess
import json
import contextlib
import os
import httpx
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional

# --- IMPORT CORE ---
from app.core.config import settings
from app.core.database import init_db, get_db_connection

# --- MONITORING ERREURS (SENTRY) ---
import sentry_sdk

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.1,
    )

# --- RATE LIMITING ---
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter

# --- IMPORT DES ROUTES ---
from app.routes import admin, viewers, api, announcements, clips, stats, public, overlays, polls, rewards, admin_vips, api_deck, labels_routes, partners, admin_commands
from app.routes.credits import router as credits_router
from app.routes.premium import router as premium_router
from app.routes.games import router as games_router, init_games_tables
from app.routes.admin_auth import router as admin_auth_router
from app.routes.admin_games import router as admin_games_router
from app.routes.admin_discord_mod import router as admin_discord_mod_router
from app.routes.felixdle import (
    public_router as felixdle_public_router,
    admin_router as felixdle_admin_router,
    init_felixdle_tables,
    felixdle_scheduler_routine,
)

# --- IMPORT DES SERVICES ---
from app.services.twitch_service import twitch_bot
from app.services.live_monitor import check_twitch_lives_routine
from app.services.eventsub_service import eventsub_routine
from app.services.unfollow_monitor import unfollow_monitor_routine
from app.services.stats_service import update_time_loop, update_twitch_stats_loop
from app.services.trophy_engine import start_trophy_engine
from app.services.games_scheduler import games_scheduler_routine
from app.services.discord_mod_service import discord_mod_bot, start_discord_mod_bot, init_discord_mod_tables, birthday_check_routine
from app.services.tiktok_monitor import tiktok_monitor_routine
from app.services.youtube_monitor import youtube_monitor_routine
from app.services.bot_health_service import (
    init_bot_health_table,
    check_for_previous_crash_and_alert,
    clear_crash_marker,
)

# --- IMPORT DES REPERTOIRES ---
from app.repositories import viewer_repo

# ==========================================
# MODÈLES DE DONNÉES (POUR PAGE INFOS)
# ==========================================
class RuleItem(BaseModel):
    emoji: str
    text: str
    is_danger: bool = False

class ScheduleItem(BaseModel):
    day_index: int
    day_name: str
    time: str
    event: str

class ChannelInfoUpdate(BaseModel):
    about_text: str
    social_discord: str
    social_youtube: str
    social_twitch: str
    social_tiktok: str
    social_tips: str
    rules: List[RuleItem]
    schedule: List[ScheduleItem]

# --- CONFIGURATION DU LOGGING ---
logger = logging.getLogger("masthbot.fastapi")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("websockets.server").setLevel(logging.WARNING)

node_process = None
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- GESTION DU CYCLE DE VIE (LIFESPAN) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global node_process
    logger.info("🚀 [STARTUP] Démarrage de Masthbot V2...")

    # 🔌 LE CÂBLE MAGIQUE ENTRE LE WEB ET TWITCH :
    app.state.bot = twitch_bot

    # 1. Initialisation Database
    await init_db()
    from app.services import partners_service
    await partners_service.run_partners_migrations()
    await viewer_repo.init_tables()
    await init_games_tables()
    await init_felixdle_tables()
    await init_discord_mod_tables()
    await init_bot_health_table()
    logger.info("✅ [DATABASE] Tables PostgreSQL initialisées avec succès !")

    # 1.5 Détection d'un crash précédent (alerte Discord si le process n'a pas été arrêté proprement)
    await check_for_previous_crash_and_alert()

    # 2. Lancement des services Twitch
    asyncio.create_task(twitch_bot.start())
    asyncio.create_task(check_twitch_lives_routine())
    asyncio.create_task(eventsub_routine())
    asyncio.create_task(unfollow_monitor_routine())
    asyncio.create_task(update_time_loop())
    asyncio.create_task(update_twitch_stats_loop())
    asyncio.create_task(start_trophy_engine())
    asyncio.create_task(games_scheduler_routine())
    asyncio.create_task(felixdle_scheduler_routine())
    asyncio.create_task(start_discord_mod_bot())
    asyncio.create_task(tiktok_monitor_routine())
    asyncio.create_task(youtube_monitor_routine())
    asyncio.create_task(birthday_check_routine())

    # 3. Lancement de l'overlay Node.js
    server_js_path = os.path.join(BASE_DIR, "server.js")
    if os.path.exists(server_js_path):
        try:
            node_process = subprocess.Popen(["node", server_js_path], cwd=BASE_DIR)
        except Exception as e:
            logger.error(f"❌ Impossible de lancer Node.js: {e}")

    try:
        yield
    finally:
        logger.info("🛑 [SHUTDOWN] Arrêt des services...")
        clear_crash_marker()
        if node_process:
            node_process.terminate()
        with contextlib.suppress(Exception):
            if hasattr(twitch_bot, '_connection') and twitch_bot._connection:
                await twitch_bot.close()
        with contextlib.suppress(Exception):
            if not discord_mod_bot.is_closed():
                await discord_mod_bot.close()

# --- INITIALISATION APP ---
app = FastAPI(title="MasthomBot V2", version="2.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# =====================================================================
# 🌐 CONFIGURATION CORS
# =====================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fel-x.icu"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

@app.exception_handler(Exception)
async def validation_exception_handler(request, exc):
    logger.error(f"❌ [UNHANDLED] {request.method} {request.url.path} : {exc}", exc_info=exc)
    if settings.SENTRY_DSN:
        sentry_sdk.capture_exception(exc)
    detail = str(exc) if settings.ENVIRONMENT != "production" else "Erreur interne du serveur."
    return JSONResponse(
        status_code=500,
        content={"detail": detail},
        headers={"Access-Control-Allow-Origin": "*"}
    )

@app.exception_handler(HTTPException)
async def admin_auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and request.url.path.startswith("/admin"):
        if request.headers.get("accept", "").find("text/html") != -1:
            return RedirectResponse(url="/admin/login", status_code=303)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# ==========================================
# MONTAGE DES DOSSIERS ET ROUTES
# ==========================================

static_path = os.path.join(BASE_DIR, "app", "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Branchement des Routes
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(viewers.router)
app.include_router(api.router)
app.include_router(announcements.router)
app.include_router(stats.router)
app.include_router(overlays.router)
app.include_router(polls.router)
app.include_router(credits_router)
app.include_router(rewards.router)
app.include_router(admin_vips.router)
app.include_router(api_deck.router)
app.include_router(labels_routes.router)
app.include_router(clips.router)
app.include_router(admin_commands.router)
app.include_router(premium_router)
app.include_router(games_router)
app.include_router(admin_auth_router)
app.include_router(admin_games_router)
app.include_router(felixdle_public_router)
app.include_router(felixdle_admin_router)
app.include_router(admin_discord_mod_router)
app.include_router(partners.router)

# ==========================================
# ROUTES API : INFORMATIONS DE LA CHAÎNE (DASHBOARD ADMIN)
# ==========================================
@app.get("/api/v1/channel-info")
async def get_channel_info():
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT * FROM channel_info WHERE id=1")
        row = await cursor.fetchone()
        
        if not row:
            return {"error": "Infos introuvables"}
            
        return {
            "about_text": row["about_text"],
            "social_discord": row["social_discord"],
            "social_youtube": row["social_youtube"],
            "social_twitch": row["social_twitch"],
            "social_tiktok": row["social_tiktok"],
            "social_tips": row["social_tips"],
            "rules": json.loads(row["rules_json"]),
            "schedule": json.loads(row["schedule_json"])
        }

@app.post("/api/v1/channel-info")
async def update_channel_info(info: ChannelInfoUpdate):
    async with get_db_connection() as conn:
        await conn.execute("""
            UPDATE channel_info SET 
                about_text = $1, social_discord = $2, social_youtube = $3, 
                social_twitch = $4, social_tiktok = $5, social_tips = $6, 
                rules_json = $7, schedule_json = $8
            WHERE id = 1
        """, (
            info.about_text, info.social_discord, info.social_youtube,
            info.social_twitch, info.social_tiktok, info.social_tips,
            json.dumps([r.model_dump() if hasattr(r, "model_dump") else r.dict() for r in info.rules]), 
            json.dumps([s.model_dump() if hasattr(s, "model_dump") else s.dict() for s in info.schedule])
        ))
    return {"status": "success", "message": "Informations de la chaîne mises à jour !"}


# ==========================================
# ROUTES API : AUTRES
# ==========================================
@app.get("/api/felix/toggle")
async def toggle_felix():
    state_file = os.path.join(BASE_DIR, "felix_state.txt")
    actuel = False
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                actuel = (f.read().strip() == "1")
        except Exception:
            actuel = False

    nouvel_etat = not actuel
    with open(state_file, "w") as f:
        f.write("1" if nouvel_etat else "0")

    return {"status": "success", "is_enabled": nouvel_etat}


if __name__ == "__main__":
    import uvicorn
    import logging

    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

    config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=8000, 
        loop="asyncio",
        access_log=False,
        log_level="warning"
    )
    
    server = uvicorn.Server(config)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(server.serve())
