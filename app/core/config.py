import os
import sys
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

_THIS_FILE = os.path.abspath(__file__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE)))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=env_path)

#env_path = "/home/thomas/masthom/BOT_V2/.env"
#load_dotenv(dotenv_path=env_path)
#DEEPL_API_KEY: str = os.getenv("DEEPL_API_KEY", "")
# =================================================================
# 1. UTILITAIRE DE NETTOYAGE
# =================================================================
def get_clean_env(key, default=None):
    val = os.getenv(key, default)
    if val is None: return default
    if not isinstance(val, str): return val
    clean = val.strip().strip("'").strip('"').replace('\\_', '_')
    if key in ["TWITCH_BOT_OAUTH_TOKEN", "TWITCH_SCOPES", "TWITCH_ACCESS_TOKEN", "TWITCH_OAUTH_TOKEN"]:
        clean = clean.split('>')[0]
    return clean.strip()

# =================================================================
# 2. CHEMINS SYSTÈME (FIX CRITIQUE)
# =================================================================
# Racine du projet (/home/thomas/masthom/BOT_V2)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#BASE_DIR = "/home/thomas/masthom/BOT_V2"

# Dossiers pour les JSON
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
#DATA_DIR = "/home/thomas/masthom/BASE_JSON"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

class Settings(BaseSettings):
    """
    Configuration centrale du bot. 
    Intègre les constantes système et les variables d'environnement.
    """
    # --- CHEMINS ET LOGS ---
    BASE_DIR: str = BASE_DIR
    DATA_DIR: str = DATA_DIR
    LOG_FILE_PATH: str = os.path.join(BASE_DIR, "app_bot.log")
    TWITCH_CHAT_LOG_FILE: str = os.path.join(BASE_DIR, "twitch_chat.log")
    DEEPL_API_KEY: str = get_clean_env("DEEPL_API_KEY", "")

    # --- FICHIERS JSON ---
    OVERLAY_CONFIG_FILE: str = os.path.join(DATA_DIR, "overlay_config.json")
    STREAMERS_FILE: str = os.path.join(DATA_DIR, "streamers.json")
    VIP_LIST_PATH: str = os.path.join(DATA_DIR, "vip_list.json")

    # --- CONFIGURATION TWITCH ---
    TWITCH_CHANNEL: str = get_clean_env("TWITCH_CHANNEL", "#masthom_")
    TWITCH_USERNAME: str = get_clean_env("TWITCH_USERNAME", "masthom_")
    TWITCH_CLIENT_ID: str = get_clean_env("TWITCH_CLIENT_ID", "")
    TWITCH_CLIENT_SECRET: str = get_clean_env("TWITCH_CLIENT_SECRET", "")
    TWITCH_OAUTH_TOKEN: str = get_clean_env("TWITCH_OAUTH_TOKEN", "")
    TWITCH_BOT_USERNAME: str = get_clean_env("TWITCH_BOT_USERNAME", "Felix")
    TWITCH_BOT_OAUTH_TOKEN: str = get_clean_env("TWITCH_BOT_OAUTH_TOKEN", "")
    TWITCH_BROADCASTER_ID: str = get_clean_env("TWITCH_BROADCASTER_ID", "")
    
    # --- CONFIGURATION DISCORD ---
    DISCORD_TOKEN: str = get_clean_env("DISCORD_TOKEN", "")
    GUILD_ID: str = get_clean_env("GUILD_ID", "")
    NOTIF_LIVE_CHANNEL_ID: str = get_clean_env("NOTIF_LIVE_CHANNEL_ID", "")
    STREAMERS_CHANNEL_ID: str = get_clean_env("STREAMERS_CHANNEL_ID", "")
    CLIP_CHANNEL_ID: str = get_clean_env("CLIP_CHANNEL_ID", "")
    ANNONCE_CHANNEL_ID: str = get_clean_env("ANNONCE_CHANNEL_ID", "")
    FAQ_CHANNEL_ID: str = get_clean_env("FAQ_CHANNEL_ID", "")
    PLANNING_CHANNEL_ID: str = get_clean_env("PLANNING_CHANNEL_ID", "1137293575026126898")
    POLLS_DISCORD_CHANNEL_ID: str = get_clean_env("POLLS_DISCORD_CHANNEL_ID", "1509812594662183035")
    TROPHY_DISCORD_CHANNEL_ID: str = get_clean_env("TROPHY_DISCORD_CHANNEL_ID", "")
    MODERATION_LOG_CHANNEL_ID: str = get_clean_env("MODERATION_LOG_CHANNEL_ID", "1399730073183191090")
    POLAROID_CHANNEL_ID: str = get_clean_env("POLAROID_CHANNEL_ID", "")

    # --- SERVICES EXTERNES ---
    OPENAI_API_KEY: str = get_clean_env("OPENAI_API_KEY", "")

    # --- AUTHENTIFICATION PANEL ADMIN ---
    ADMIN_PASSWORD: str = get_clean_env("ADMIN_PASSWORD", "")
    ADMIN_SESSION_SECRET: str = get_clean_env("ADMIN_SESSION_SECRET", "")

    # --- MONITORING ERREURS (SENTRY) ---
    SENTRY_DSN: str = get_clean_env("SENTRY_DSN", "")
    ENVIRONMENT: str = get_clean_env("ENVIRONMENT", "production")
    
    # --- OVERLAY NODE.JS (OBS local, port 3005) ---
    OVERLAY_NODE_URL: str = get_clean_env("OVERLAY_NODE_URL", "http://192.168.1.32:3005").rstrip("/")

    # --- OBS WEB SOCKET ---
    OBS_HOST: str = get_clean_env("OBS_HOST", "127.0.0.1")
    OBS_PORT: int = int(get_clean_env("OBS_PORT", 4455))
    OBS_PASSWORD: str = get_clean_env("OBS_PASSWORD", "")

    class Config:
        env_file = env_path
        extra = "ignore"

# Création de l'instance unique
settings = Settings()
