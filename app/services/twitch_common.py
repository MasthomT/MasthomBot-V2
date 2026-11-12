"""Éléments partagés par le bot Twitch : envoi sécurisé, état de session, analyse de !play."""

import logging
import re
import time

logger = logging.getLogger("masthbot.twitch")

# Set pour ne souhaiter l'anniversaire qu'une seule fois par session de bot
_birthday_wished: set = set()
_permitted_users: set = set()

# Suivi des échecs d'envoi IRC ("closing transport" bloqué en continu, pas juste une
# reconnexion transitoire) — voir le filet de sécurité dans watchdog_timer ci-dessous.
_send_failure_since: float | None = None

# ── Lecteur unifié (!play) ─────────────────────────────────
_TIKTOK_LINK_RE = re.compile(r"https?://\S*tiktok\.com\S*", re.IGNORECASE)   # tiktok.com, vm.tiktok.com, vt.tiktok.com
# YouTube (vidéo, short, youtu.be) et Instagram (reel, post) : téléchargés puis lus comme un TikTok.
_VIDEO_LINK_RE = re.compile(r"https?://(?:[\w-]+\.)*(?:youtube\.com|youtu\.be|instagram\.com|instagr\.am)\S*", re.IGNORECASE)


def classify_play_input(content):
    """Reconnaît ce que l'on veut lire.
    → ("tiktok", url | None)               url None = dernier TikTok connu
    → ("video", url)                       lien YouTube ou Instagram
    → ("clip", {"slug", "query"})          lien de clip Twitch ou mots du titre ; tout à None = dernier clip
    Les mots-clés « clip » et « tiktok » (seuls ou devant le reste) forcent le type."""
    text = (content or "").strip()
    forced = None
    first, _, rest = text.partition(" ")
    if first.lower() in ("clip", "tiktok"):
        forced, text = first.lower(), rest.strip()

    link = _TIKTOK_LINK_RE.search(text)
    if forced == "tiktok" or (forced is None and link):
        return "tiktok", (link.group(0) if link else None)

    video_link = _VIDEO_LINK_RE.search(text)
    if forced is None and video_link:
        return "video", video_link.group(0)

    slug = query = None
    if text:
        twitch_link = next((t for t in text.split() if "twitch.tv" in t.lower()), None)
        if twitch_link:
            slug = twitch_link
        else:
            query = text
    return "clip", {"slug": slug, "query": query}


async def safe_send(channel, content: str) -> bool:
    """Envoie un message en sécurisant la longueur et le contenu.
    Retourne False en cas d'échec, pour permettre à l'appelant de retenter
    plutôt que de considérer le message comme envoyé à tort."""
    global _send_failure_since
    if not content or not content.strip():
        return False # On ne fait rien si le message est vide

    # Tronquage à 500 caractères max
    if len(content) > 500:
        content = content[:497] + "..."

    try:
        await channel.send(content)
        _send_failure_since = None  # succès : la connexion écrit de nouveau normalement
        return True
    except Exception as e:
        # "closing transport" : Twitch IRC force une reconnexion périodique, c'est
        # transitoire et attendu — pas la peine de polluer les logs en ERROR pour ça.
        # Mais si ça persiste (voir watchdog_timer), la connexion est réellement morte.
        if "closing transport" in str(e):
            logger.warning(f"⚠️ Envoi différé (reconnexion IRC en cours) : {e}")
            if _send_failure_since is None:
                _send_failure_since = time.time()
        else:
            logger.error(f"❌ Erreur lors de l'envoi du message : {e}")
        return False
