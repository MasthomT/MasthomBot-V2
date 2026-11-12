"""Accès à OBS depuis le bot Python — via server.js, seul client OBS.

Avant, le bot Python ouvrait ses propres connexions OBS (obsws-python) : un écouteur
de scène permanent (qui relançait la BRB déjà lancée par server.js), une connexion
neuve à chaque capture d'écran, et une à chaque interrogation du Stream Deck (jusqu'à
une par seconde). server.js garde déjà une connexion OBS permanente : on lui délègue
tout par HTTP local.

Méthodes synchrones (urllib) : elles sont appelées via asyncio.to_thread.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import settings

logger = logging.getLogger("masthbot.obs")

DEFAULT_STATUS = {"connected": False, "scene": "main", "mic_muted": False, "cam_visible": True}


class OBSService:
    def __init__(self):
        self.node_url = settings.OVERLAY_NODE_URL

    def _get(self, path: str, params: dict | None = None, timeout: float = 5):
        url = f"{self.node_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _screenshot(self, source: str | None, width: int, height: int, quality: int):
        try:
            data = self._get("/api/obs/screenshot",
                             {"source": source, "width": width, "height": height, "quality": quality}, timeout=10)
            return data.get("image") or None
        except urllib.error.HTTPError as e:
            if e.code != 503:  # 503 = OBS fermé : situation normale hors stream
                logger.warning(f"⚠️ [OBS] Capture impossible ({source or 'scène en cours'}) : HTTP {e.code}")
        except Exception as e:
            logger.debug(f"👀 [OBS] Capture indisponible : {e}")
        return None

    def take_screenshot(self):
        """Capture de la scène en cours (base64 JPEG 1280×720), ou None si OBS est indisponible."""
        return self._screenshot(None, 1280, 720, 70)

    def take_source_screenshot(self, source_name: str, width: int = 720, height: int = 900):
        """Capture d'une source précise (ex. la webcam), indépendamment de la scène affichée."""
        return self._screenshot(source_name, width, height, 85)

    def get_status(self) -> dict:
        """État d'OBS : scène, micro coupé, webcam et Féli'cam visibles."""
        try:
            data = self._get("/api/obs/status", timeout=2)
            return {**DEFAULT_STATUS, **data} if data.get("connected") else dict(DEFAULT_STATUS)
        except Exception:
            return dict(DEFAULT_STATUS)

    def run_action(self, action: str, **params) -> bool:
        """Exécute une action OBS (mêmes noms que les commandes du site : scene_switch,
        source_toggle, toggle_mute, hotkey_sequence…)."""
        body = json.dumps({"type": "obs_command", "details": {"action": action, **params}}).encode("utf-8")
        req = urllib.request.Request(f"{self.node_url}/api/trigger", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5):
                return True
        except urllib.error.HTTPError as e:
            try:
                reason = json.loads(e.read().decode("utf-8")).get("message", "")
            except Exception:
                reason = ""
            logger.warning(f"⚠️ [OBS] Action {action} refusée : {reason or f'HTTP {e.code}'}")
        except Exception as e:
            logger.warning(f"⚠️ [OBS] Action {action} impossible : {e}")
        return False


obs_service = OBSService()
