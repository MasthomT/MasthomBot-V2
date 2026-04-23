import logging
import json
import os

logger = logging.getLogger("masthbot.credits")

# Fichier physique pour sauvegarder le générique en cas de redémarrage
SESSION_FILE = "/home/masthom/BOT_V2/credits_session.json"

class CreditsService:
    def __init__(self):
        self.session_watchtime = {}
        self.session_messages = {}
        self.categories = {
            "subscribers": {}, "gifters": {}, "bits": {}, "raiders": {},
            "followers": {}, "moderators": {}, "vips": {}, "chatters": {}, "viewers": {}
        }
        self.config = {
            "main_title": "MERCI À TOUS !",
            "subtitle": "À BIENTÔT SUR LE LIVE",
            "duration": 60,
            "order": ["subscribers", "gifters", "bits", "raiders", "followers", "vips", "moderators", "chatters", "viewers"]
        }
        self._load_session()

    def _load_session(self):
        """Restaure les données si le bot a été redémarré."""
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.session_watchtime = data.get("session_watchtime", self.session_watchtime)
                    self.session_messages = data.get("session_messages", self.session_messages)
                    self.categories = data.get("categories", self.categories)
                    self.config = data.get("config", self.config)
            except Exception as e:
                logger.error(f"❌ Erreur lecture session générique: {e}")

    def _save_session(self):
        """Sauvegarde les données dans un fichier de secours."""
        try:
            data = {
                "session_watchtime": self.session_watchtime,
                "session_messages": self.session_messages,
                "categories": self.categories,
                "config": self.config
            }
            with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde session générique: {e}")

    def add_watchtime(self, name, minutes=1):
        """Ajoute le temps de présence et inscrit par défaut dans Viewers."""
        n = name.lower()
        self.session_watchtime[n] = self.session_watchtime.get(n, 0) + minutes
        
        # On l'ajoute dans viewers par défaut. Le grand nettoyage se fera à l'affichage !
        if n not in self.categories["viewers"]:
            self.categories["viewers"][n] = {"name": name, "label": ""}
        self._save_session()

    def log_event(self, category, name, label=""):
        """Ajoute officiellement un VIP, Modo, Chatter ou Sub."""
        if category not in self.categories:
            return

        n = name.lower()
        
        # On incrémente les messages envoyés pendant le stream
        if category in ["chatters", "moderators", "vips"]:
            self.session_messages[n] = self.session_messages.get(n, 0) + 1
            
        self.categories[category][n] = {"name": name, "label": label}
        self._save_session()

    def update_config(self, new_config):
        self.config.update(new_config)
        self._save_session()

    def get_stats(self):
        """
        Prépare les données pour l'overlay.
        C'EST ICI QUE LA MAGIE OPÈRE : Nettoyage des doublons et ajout du temps !
        """
        data = {}

        # 1. On identifie TOUS ceux qui ont parlé ou qui ont un badge (VIP, Modos, Chatters)
        higher_tiers = set()
        for cat in ["moderators", "vips", "chatters"]:
            for n in self.categories[cat].keys():
                higher_tiers.add(n)

        # 2. On construit les listes finales
        for cat, users in self.categories.items():
            cat_list = []
            for n, info in users.items():
                
                # =========================================================
                # 🛑 LE FILTRE ANTI-DOUBLONS
                # Si on est en train de lister les "Viewers", mais que 
                # la personne est DÉJÀ un VIP, un Modo ou un Chatter, ON L'IGNORE.
                # Ainsi, la catégorie Viewers devient STRICTEMENT réservée aux Lurkers !
                # =========================================================
                if cat == "viewers" and n in higher_tiers:
                    continue

                final_label = info["label"]
                
                # 💬 INJECTION DU NOMBRE DE MESSAGES (Pour Modos, VIPs, Chatters)
                if cat in ["chatters", "moderators", "vips"]:
                    msg_count = self.session_messages.get(n, 1)
                    msg_str = f"{msg_count} message{'s' if msg_count > 1 else ''}"
                    if final_label:
                        final_label = f"{final_label} • 💬 {msg_str}"
                    else:
                        final_label = f"💬 {msg_str}"
                        
                # ⏱️ INJECTION DU WATCHTIME POUR LES AUTRES
                elif cat in ["viewers", "subscribers", "gifters", "bits"]:
                    wt = self.session_watchtime.get(n, 0)
                    if wt > 0:
                        wt_str = f"{wt} min" if wt < 60 else f"{wt//60}h{wt%60:02d}"
                        if final_label:
                            final_label = f"{final_label} • ⏱️ {wt_str}"
                        else:
                            final_label = f"⏱️ {wt_str}"
                            
                cat_list.append({"name": info["name"], "label": final_label})
            
            # Tri alphabétique propre
            data[cat] = sorted(cat_list, key=lambda x: x["name"].lower())
            
        return data

    def reset_session(self):
        """Vide le générique."""
        self.session_watchtime = {}
        self.session_messages = {}
        for cat in self.categories:
            self.categories[cat] = {}
        self._save_session()

credits_service = CreditsService()
