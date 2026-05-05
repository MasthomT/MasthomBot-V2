import asyncio
import subprocess
import contextlib
import os
import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

# --- IMPORT CORE ---
from app.core.database import db_writer_worker, DB_PATH

# --- IMPORT DES ROUTES ---
from app.routes import admin, viewers, api, announcements, stats, public, overlays, polls, rewards, admin_vips, api_deck, labels_routes
from app.routes.credits import router as credits_router 

# --- IMPORT DES SERVICES ---
from app.services.twitch_service import twitch_bot
from app.services.live_monitor import check_twitch_lives_routine
from app.services.eventsub_service import eventsub_routine
from app.services.unfollow_monitor import unfollow_monitor_routine
from app.services.stats_service import update_time_loop, update_twitch_stats_loop

# --- IMPORT DES REPERTOIRES ---
from app.repositories import viewer_repo

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

    # 1. Initialisation Database
    await viewer_repo.init_tables()
    logger.info("✅ [DATABASE] Tables SQLite initialisées.")

    # 2. Lancement des services Twitch
    asyncio.create_task(twitch_bot.start())
    asyncio.create_task(check_twitch_lives_routine())
    asyncio.create_task(eventsub_routine())
    asyncio.create_task(unfollow_monitor_routine())
    asyncio.create_task(update_time_loop())
    asyncio.create_task(update_twitch_stats_loop())
    asyncio.create_task(db_writer_worker(DB_PATH))

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
        if node_process:
            node_process.terminate()
        with contextlib.suppress(Exception):
            if hasattr(twitch_bot, '_connection') and twitch_bot._connection:
                await twitch_bot.close()

app = FastAPI(title="MasthomBot V2", version="2.0.0", lifespan=lifespan)

# =====================================================================
# 🌐 CONFIGURATION CORS ULTRA-COMPLÈTE
# =====================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://fel-x.vercel.app",
        "https://prime-nearby-tick.ngrok-free.app", # Ton tunnel Ngrok officiel
        "http://localhost:3000"
    ],
    allow_credentials=True, # Autorise les échanges sécurisés (cookies/headers)
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
