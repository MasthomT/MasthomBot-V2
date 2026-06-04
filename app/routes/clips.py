import logging
import aiohttp
import asyncio
import yt_dlp
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from app.routes.overlays import trigger_overlay_event
from app.core.config import settings

logger = logging.getLogger("masthbot.clips")
router = APIRouter(prefix="/admin", tags=["clips"])
templates = Jinja2Templates(directory="app/templates")

BROADCASTER_ID = "439356462"  # Ton vrai ID Twitch
LAST_PLAYED_CLIPS = []

# Fonction magique qui extrait le vrai .mp4 (contourne toutes les sécurités Twitch)
def extract_mp4_url(clip_id: str):
    clip_url = f"https://clips.twitch.tv/{clip_id}"
    ydl_opts = {'quiet': True, 'format': 'best[ext=mp4]/best'}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clip_url, download=False)
            return info.get('url')
    except Exception as e:
        logger.error(f"Erreur yt-dlp pour {clip_id}: {e}")
        return None

@router.get("/clips_manager", response_class=HTMLResponse)
async def clips_manager_page(request: Request, start_date: str = None, end_date: str = None):
    clips = []
    if start_date and end_date:
        started_at = f"{start_date}T00:00:00Z"
        ended_at = f"{end_date}T23:59:59Z"
        
        headers = {
            "Client-Id": settings.TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {settings.TWITCH_OAUTH_TOKEN}" 
        }
        url = f"https://api.twitch.tv/helix/clips?broadcaster_id={BROADCASTER_ID}&started_at={started_at}&ended_at={ended_at}&first=50"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        clips = sorted(data.get("data", []), key=lambda c: c["created_at"])

        except Exception as e:
            logger.error(f"❌ Erreur critique : {e}")

    return templates.TemplateResponse(
        request=request, name="admin/clips_manager.html", 
        context={"request": request, "clips": clips, "start_date": start_date, "end_date": end_date}
    )

class ClipData(BaseModel):
    id: str
    thumb: str
    duration: float
    title: str       
    creator: str     

class QuadClipsPayload(BaseModel):
    clips: list[ClipData] # Doit accepter une liste (peu importe le nombre d'éléments)

@router.post("/clips/trigger_quad")
async def trigger_quad_clips(payload: QuadClipsPayload):
    global LAST_PLAYED_CLIPS # On signale qu'on utilise la variable globale

    if len(payload.clips) < 1 or len(payload.clips) > 4:
        return {"error": "Tu dois sélectionner entre 1 et 4 clips."}

    # 🧠 ON MÉMORISE LES CLIPS POUR LE SONDAGE (Limité à 25 caractères par Twitch !)
    LAST_PLAYED_CLIPS = []
    for i, c in enumerate(payload.clips):
        # On crée un titre du genre "1. Mon super titre" et on coupe à 25 lettres max
        choice_title = f"{i+1}. {c.title}"[:25]
        LAST_PLAYED_CLIPS.append(choice_title)

    # --- LE RESTE DE TA FONCTION NE CHANGE PAS ---
    mp4_urls = await asyncio.gather(
        *[asyncio.to_thread(extract_mp4_url, c.id) for c in payload.clips]
    )

    if None in mp4_urls:
        return {"error": "Twitch a bloqué l'extraction d'un clip. Réessayez."}

    meta_data = [{"title": c.title, "creator": c.creator} for c in payload.clips]

    sse_data = {
        "type": "start_quad_clips",
        "urls": mp4_urls,
        "meta": meta_data
    }
    await trigger_overlay_event(sse_data)
    
    return {"status": "success"}

@router.get("/overlay/clips", response_class=HTMLResponse)
async def overlay_clips_quad(request: Request):
    return templates.TemplateResponse(
        request=request, name="clips_quad_overlay.html", context={"request": request}
    )

@router.post("/clips/start_poll")
async def start_clips_poll():
    global LAST_PLAYED_CLIPS
    
    if not LAST_PLAYED_CLIPS:
        return {"error": "Aucun clip n'a été lancé récemment !"}

    url = "https://api.twitch.tv/helix/polls"
    headers = {
        "Client-Id": settings.TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {settings.TWITCH_OAUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Préparation des données pour l'API Twitch
    data = {
        "broadcaster_id": BROADCASTER_ID,
        "title": "Quel est votre clip préféré ?",
        "choices": [{"title": title} for title in LAST_PLAYED_CLIPS],
        "duration": 180 # Durée en secondes (3 minutes)
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                if resp.status == 200:
                    return {"status": "success", "message": "Sondage lancé sur le t'chat !"}
                else:
                    error_msg = await resp.text()
                    logger.error(f"❌ Erreur Twitch Poll ({resp.status}): {error_msg}")
                    return {"error": f"Twitch a refusé la création du sondage."}
    except Exception as e:
        logger.error(f"❌ Erreur critique sondage: {e}")
        return {"error": "Erreur de connexion à Twitch."}
