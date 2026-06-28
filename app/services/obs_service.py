import logging
import threading
import time
import json
import urllib.request
import obsws_python as obs
from app.core.config import settings

logger = logging.getLogger("masthbot.obs")

class OBSService:
    def __init__(self):
        self.host = settings.OBS_HOST
        self.port = settings.OBS_PORT
        self.password = settings.OBS_PASSWORD
        self.overlay_url = getattr(settings, "OVERLAY_URL", "http://127.0.0.1:3000")

        # 🚀 On démarre l'écouteur OBS en arrière-plan dès l'allumage du bot
        threading.Thread(target=self.start_listener, daemon=True).start()

    def start_listener(self):
        """Boucle de connexion permanente à OBS. Se reconnecte automatiquement si OBS
        redémarre ou si la connexion est perdue (coupure réseau, crash OBS, etc.)."""
        if not self.host or not self.password:
            return

        first_attempt = True
        while True:
            try:
                self.event_client = obs.EventClient(host=self.host, port=self.port, password=self.password)
                self.event_client.callback.register(self.on_current_program_scene_changed)
                if first_attempt:
                    logger.info("🎧 [OBS] Écouteur activé — détection des changements de scène.")
                else:
                    logger.info("🔄 [OBS] Reconnecté après déconnexion.")
                first_attempt = False

                # obsws_python maintient la connexion en interne — on vérifie toutes les 30s
                # qu'OBS répond encore via une requête légère.
                req_client = obs.ReqClient(host=self.host, port=self.port, password=self.password)
                while True:
                    time.sleep(30)
                    try:
                        req_client.get_version()
                    except Exception:
                        logger.warning("⚠️ [OBS] Connexion perdue, tentative de reconnexion...")
                        break

            except Exception:
                if first_attempt:
                    logger.debug("👀 [OBS] Non joignable au démarrage, nouvelle tentative dans 30s.")
                time.sleep(30)

    def on_current_program_scene_changed(self, data):
        """Méthode appelée automatiquement par OBS quand la scène change"""
        scene = data.scene_name
        logger.info(f"🎬 [OBS] Nouvelle scène active : {scene}")
        
        if scene == "ON BREAK":
            logger.info("⏸️ Scène ON BREAK détectée ! Masthbot attend 1.5s qu'OBS charge la page...")
            threading.Timer(1.5, self.trigger_brb_overlay, args=["brb"]).start()
        elif scene == "END":
            logger.info("🎬 [OBS] Scène END détectée — rechargement du générique.")
            threading.Timer(1.0, self.refresh_browser_source, args=["WID_Générique"]).start()
            self.trigger_brb_overlay("main")
        else:
            self.trigger_brb_overlay("main")

    def refresh_browser_source(self, source_name: str):
        """Force le rechargement d'une Browser Source OBS."""
        try:
            cl = obs.ReqClient(host=self.host, port=self.port, password=self.password)
            cl.press_input_properties_button(source_name, "refreshnocache")
            logger.info(f"🔄 [OBS] Browser Source '{source_name}' rechargée.")
        except Exception as e:
            logger.error(f"❌ [OBS] Impossible de recharger '{source_name}' : {e}")

    def trigger_brb_overlay(self, scene_state):
        """Masthbot force la régie Node.js via les routes qui existent VRAIMENT."""
        try:
            if scene_state == "brb":
                # Masthbot force la page web à s'afficher (Node.js ira chercher les clips et les lancera tout seul !)
                req1 = urllib.request.Request("http://127.0.0.1:3005/api/trigger", method="POST")
                req1.add_header('Content-Type', 'application/json')
                data1 = json.dumps({"type": "change_scene", "scene": "brb"}).encode('utf-8')
                urllib.request.urlopen(req1, data=data1, timeout=2)
                
                logger.info("✅ [MASTHBOT] Signal envoyé : Le BRB est forcé à l'écran !")
            else:
                # Masthbot cache la page web quand on quitte la scène
                req1 = urllib.request.Request("http://127.0.0.1:3005/api/trigger", method="POST")
                req1.add_header('Content-Type', 'application/json')
                data1 = json.dumps({"type": "change_scene", "scene": "main"}).encode('utf-8')
                urllib.request.urlopen(req1, data=data1, timeout=2)
                
        except Exception as e:
            logger.error(f"❌ [MASTHBOT] Erreur de communication avec Node : {e}")

    # =======================================================
    # TES ANCIENNES FONCTIONS (INTACTES ET CORRIGÉES)
    # =======================================================

    def take_screenshot(self):
        """Prend un screenshot de la scène actuelle et le retourne en base64"""
        if not self.host or not self.password:
            return None

        try:
            cl = obs.ReqClient(host=self.host, port=self.port, password=self.password)
            current_scene = cl.get_current_program_scene().scene_name

            resp = cl.get_source_screenshot(
                source_name=current_scene,
                image_format="jpeg",
                image_width=1280,
                image_height=720,
                image_compression_quality=70
            )

            base64_data = resp.image_data.split(",")[1] if "," in resp.image_data else resp.image_data
            return base64_data

        except Exception as e:
            logger.debug(f"👀 OBS Vision non disponible : {e}")
            return None

    def get_deck_status(self):
        """Récupère l'état d'OBS pour allumer les lumières du Stream Deck"""
        try:
            cl = obs.ReqClient(host=self.host, port=self.port, password=self.password)
            
            # 1. Scène Actuelle
            scene_resp = cl.get_current_program_scene()
            scene_name = scene_resp.current_program_scene_name

            # 2. Statut du Micro
            mute_resp = cl.get_input_mute("Micro")
            is_muted = mute_resp.input_muted

            # 3. Statut Webcam
            cam_visible = True
            items_resp = cl.get_scene_item_list(scene_name)
            for item in items_resp.scene_items:
                if item['sourceName'] == "WEBCAM":
                    cam_visible = item['sceneItemEnabled']
                    break

            return {
                "scene": scene_name,
                "mic_muted": is_muted,
                "cam_visible": cam_visible
            }
        except Exception:
            return {"scene": "main", "mic_muted": False, "cam_visible": True}

obs_service = OBSService()
