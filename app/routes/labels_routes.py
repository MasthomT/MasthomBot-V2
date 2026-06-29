import os
import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}
from app.services.label_service import LABELS_DIR, register_label_client, unregister_label_client
# On crée le routeur FastAPI (l'équivalent du Blueprint)
router = APIRouter()

# 📡 Flux SSE : le serveur pousse les changements de label en temps réel aux overlays.
@router.get('/api/labels/stream')
async def labels_stream(request: Request):
    queue: asyncio.Queue = asyncio.Queue()
    register_label_client(queue)

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                payload = await queue.get()
                yield f"data: {json.dumps(payload)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unregister_label_client(queue)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=NO_CACHE)

# Configuration des chemins
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LABELS_DIR = os.path.join(BASE_DIR, "labels")

# On indique à FastAPI où trouver tes fichiers HTML (templates)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))

def lire_fichier_label(nom_fichier):
    """Fonction utilitaire pour lire le contenu d'un fichier texte."""
    chemin = os.path.join(LABELS_DIR, nom_fichier)
    if os.path.exists(chemin):
        with open(chemin, "r", encoding="utf-8") as f:
            return f.read()
    return "En attente..."

# 🌐 ROUTE 1 : Affichage du design (Ce que tu mets dans OBS)
# En FastAPI, les variables d'URL s'écrivent avec des accolades {type_label}
@router.get('/overlay/label/{type_label}', response_class=HTMLResponse)
async def overlay_label(request: Request, type_label: str):
    icones = {
        "follow": "fa-heart",
        "sub": "fa-star",
        "subgift": "fa-gift",
        "bits": "fa-gem",
        "raid": "fa-users"
    }
    icone_choisie = icones.get(type_label, "fa-comment-dots")
    
    # On retourne le template HTML en lui passant la requête et nos variables
    return templates.TemplateResponse(
        request=request,
        name="labels/label_anime.html",
        context={
            "type_label": type_label, 
            "icone": icone_choisie
        }
    )

# 📡 ROUTE 2 : Mini API (Pour que le JavaScript interroge le serveur en silence)
@router.get('/api/label/{type_label}')
async def api_label(type_label: str):
    fichiers = {
        "follow": "dernier_follow.txt",
        "sub": "dernier_sub.txt",
        "subgift": "dernier_subgift.txt",
        "bits": "dernier_bits.txt",
        "raid": "dernier_raid.txt",
        "viewers": "viewers.txt",
        "subs": "nombre_subs.txt"  # 👈 C'est cette ligne qui évite le 404 sur les données !
    }
    
    # On cherche le nom du fichier correspondant à la demande
    nom_fichier = fichiers.get(type_label)
    
    if nom_fichier:
        # Si le fichier est connu, on le lit
        texte = lire_fichier_label(nom_fichier)
        
        # Sécurité : si le fichier est vide ou en attente, on affiche 0 pour les compteurs
        if not texte or texte == "En attente...":
            texte = "0" if type_label in ["viewers", "subs"] else ""
    else:
        # Si le type_label n'est pas dans notre dictionnaire (ce qui causait l'Erreur de type)
        texte = "0" 
        
    return JSONResponse({"texte": texte}, headers=NO_CACHE)

@router.get('/overlay/heure', response_class=HTMLResponse)
async def overlay_heure(request: Request):
    # On indique à FastAPI de chercher dans le sous-dossier "labels"
    return templates.TemplateResponse(
        request=request, 
        name="labels/heure.html", # 👈 Modification de l'adresse ici
        context={}
    )

# 📡 API : Lecture silencieuse du fichier heure.txt
@router.get('/api/heure')
async def api_heure():
    texte = lire_fichier_label("heure.txt")
    return JSONResponse({"texte": texte}, headers=NO_CACHE)

# ==========================================
# 🌐 ROUTES : VIEWERS ET FOLLOWERS
# ==========================================

# Affichage OBS pour les Followers
@router.get('/overlay/followers', response_class=HTMLResponse)
async def overlay_followers(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="labels/followers.html", 
        context={}
    )

# Lecture API silencieuse pour les Followers
@router.get('/api/followers')
async def api_followers():
    texte = lire_fichier_label("followers.txt")
    return JSONResponse({"texte": texte}, headers=NO_CACHE)

@router.get('/api/label/viewers_count')
async def get_viewers_label():
    """Route spécifique pour l'overlay qui lit le fichier texte."""
    file_path = os.path.join(LABELS_DIR, "viewers.txt")
    
    if not os.path.exists(file_path):
        return JSONResponse({"texte": "0"}, headers=NO_CACHE)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            contenu = f.read().strip()
            # On s'assure de renvoyer une chaîne de caractères propre
            return JSONResponse({"texte": str(contenu) if contenu else "0"}, headers=NO_CACHE)
    except Exception:
        return JSONResponse({"texte": "0"}, headers=NO_CACHE)

@router.get('/overlay/viewers', response_class=HTMLResponse)
async def overlay_viewers(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="labels/viewers.html", 
        context={}
    )

@router.get('/overlay/subs', response_class=HTMLResponse)
async def overlay_subs(request: Request):
    # Indique au serveur de renvoyer ton fichier subs.html
    return templates.TemplateResponse(
        request=request, 
        name="labels/subs.html", 
        context={}
    )
