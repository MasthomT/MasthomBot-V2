import os
import logging

logger = logging.getLogger(__name__)

# 🛠️ SOLUTION RADICALE : On écrit le chemin en dur pour éviter les erreurs
# C'est l'endroit exact où ton bot va travailler.
LABELS_DIR = "/home/masthom/BOT_V2/labels"

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
