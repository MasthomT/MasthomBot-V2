import os
import asyncio
import logging

logger = logging.getLogger(__name__)

# 🛠️ SOLUTION RADICALE : On écrit le chemin en dur pour éviter les erreurs
# C'est l'endroit exact où ton bot va travailler.
LABELS_DIR = "/home/thomas/masthom/BOT_V2/labels"

# ==========================================
# 📡 PUSH TEMPS RÉEL VERS LES OVERLAYS (SSE)
# Plutôt que de laisser OBS interroger le serveur (polling fragile : cache CEF,
# timers gelés), le serveur POUSSE la nouvelle valeur dès qu'un label change.
# ==========================================
_label_clients: list[asyncio.Queue] = []

# Correspondance fichier -> type de label utilisé par les overlays
FILE_TO_TYPE = {
    "dernier_follow.txt": "follow",
    "dernier_sub.txt": "sub",
    "dernier_subgift.txt": "subgift",
    "dernier_bits.txt": "bits",
    "dernier_raid.txt": "raid",
    "viewers.txt": "viewers",
    "nombre_subs.txt": "subs",
    "followers.txt": "followers",
}

def register_label_client(queue: asyncio.Queue):
    _label_clients.append(queue)

def unregister_label_client(queue: asyncio.Queue):
    if queue in _label_clients:
        _label_clients.remove(queue)

def _broadcast_label(filename: str, content: str):
    """Pousse la nouvelle valeur à tous les overlays connectés en SSE.
    Best-effort : si on n'est pas dans la boucle asyncio, on ne fait rien
    (le polling de l'overlay prendra le relais)."""
    label_type = FILE_TO_TYPE.get(filename)
    if not label_type or not _label_clients:
        return
    payload = {"type": label_type, "texte": str(content)}
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    for q in list(_label_clients):
        try:
            loop.call_soon_threadsafe(q.put_nowait, payload)
        except Exception:
            pass

def init_labels_dir():
    """Vérifie si le dossier 'labels' existe, sinon le crée."""
    if not os.path.exists(LABELS_DIR):
        os.makedirs(LABELS_DIR, exist_ok=True)

def write_label(filename: str, content: str):
    """Écrit le contenu dans le dossier labels."""
    init_labels_dir()
    file_path = os.path.join(LABELS_DIR, filename)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(str(content))
        # On prévient instantanément les overlays connectés
        _broadcast_label(filename, content)
    except Exception as e:
        logger.error(f"❌ Erreur écriture : {e}")

def lire_fichier_label(filename: str) -> str:
    """Lit un fichier dans le dossier labels."""
    file_path = os.path.join(LABELS_DIR, filename)
    if not os.path.exists(file_path):
        return "--"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        return "--"
