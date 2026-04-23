import logging
import obsws_python as obs
from app.core.config import settings

logger = logging.getLogger("masthbot.obs")

class OBSService:
    def __init__(self):
        self.host = settings.OBS_HOST
        self.port = settings.OBS_PORT
        self.password = settings.OBS_PASSWORD

    def take_screenshot(self):
        """Prend un screenshot de la scène actuelle et le retourne en base64"""
        if not self.host or not self.password:
            return None
            
        try:
            # Connexion à OBS WebSocket (v5)
            cl = obs.ReqClient(host=self.host, port=self.port, password=self.password)
            
            # 1. Obtenir la scène courante en direct
            current_scene = cl.get_current_program_scene().scene_name
            
            # 2. Prendre le screenshot (jpeg compressé à 70% pour la vitesse et les coûts IA)
            resp = cl.get_source_screenshot(
                source_name=current_scene,
                image_format="jpeg",
                image_width=1280,
                image_height=720,
                image_compression_quality=70
            )
            
            # 3. Récupérer la chaîne Base64 propre
            base64_data = resp.image_data.split(",")[1] if "," in resp.image_data else resp.image_data
            
            return base64_data
            
        except Exception as e:
            # Reste silencieux si OBS est éteint pour ne pas polluer les logs
            logger.debug(f"👀 OBS Vision non disponible : {e}")
            return None

obs_service = OBSService()
