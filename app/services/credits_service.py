import logging
import json
import os

logger = logging.getLogger("masthbot.credits")
SESSION_FILE = "/home/thomas/masthom/BOT_V2/credits_session.json"

class CreditsService:
    def __init__(self):
        self.session_watchtime = {}
        self.session_messages = {}
        self.categories = {
            "subscribers": {}, "gifters": {}, "bits": {}, "raiders": {},
            "followers": {}, "moderators": {}, "vips": {}, "chatters": {}
        }
        
        self.config = {
            "main_title": "MERCI À TOUS !",
            "subtitle": "À BIENTÔT SUR LE LIVE",
            "duration": 60,
            "order": ["subscribers", "gifters", "bits", "raiders", "followers", "vips", "moderators", "chatters", "viewers"]
        }
        
        self._load_session()

    def _load_session(self):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.session_watchtime = data.get("session_watchtime", {})
                    self.session_messages = data.get("session_messages", {})
                    self.categories = data.get("categories", self.categories)
            except Exception as e:
                # FINI DE CACHER LES ERREURS
                logger.error(f"❌ [CREDITS FATAL] Impossible de lire le fichier JSON : {e}")

    def _save_session(self):
        try:
            data = {
                "session_watchtime": self.session_watchtime, 
                "session_messages": self.session_messages, 
                "categories": self.categories
            }
            with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"❌ [CREDITS FATAL] Impossible de sauvegarder le fichier JSON : {e}")

    def add_watchtime(self, name, minutes=1):
        self._load_session() # On recharge pour être sûr de ne pas écraser les autres
        name_lower = name.lower()
        self.session_watchtime[name_lower] = self.session_watchtime.get(name_lower, 0) + minutes
        self._save_session()

    def log_event(self, category, name, label=""):
        self._load_session()
        name_lower = name.lower()
        
        if category in self.categories:
            if name_lower in self.categories[category]:
                # Additionner les gifts/bits/raiders au lieu d'écraser
                existing = self.categories[category][name_lower]
                if category in ("gifters", "bits"):
                    try:
                        old_val = int(str(existing.get("label", "0")).split()[0])
                        new_val = int(str(label).split()[0])
                        unit = " ".join(str(label).split()[1:]) if len(str(label).split()) > 1 else ""
                        total = old_val + new_val
                        label = f"{total} {unit}".strip()
                    except (ValueError, IndexError):
                        pass
                elif category == "subscribers":
                    try:
                        old_months = int(str(existing.get("label", "1")))
                        new_months = int(str(label))
                        label = str(old_months + new_months)
                    except (ValueError, TypeError):
                        pass
            
            self.categories[category][name_lower] = {"name": name, "label": label}
            
        self.session_messages[name_lower] = self.session_messages.get(name_lower, 0) + 1
        self._save_session()

    def get_stats(self):
        self._load_session() # On lit la toute dernière version fraîche
        data = {}
        for cat, users in self.categories.items():
            cat_list = []
            for n, info in users.items():
                msg_count = self.session_messages.get(n.lower(), 0)
                cat_list.append({
                    "name": info["name"], 
                    "label": info["label"], 
                    "messages": msg_count
                })
            data[cat] = cat_list
        
        viewers_list = []
        for n, wt in self.session_watchtime.items():
            viewers_list.append({"name": n.capitalize(), "watchtime": wt})
            
        data["viewers"] = viewers_list
        return data

    def reset_session(self):
        self.session_watchtime, self.session_messages = {}, {}
        for cat in self.categories: self.categories[cat] = {}
        self._save_session()
        logger.info("♻️ [CREDITS] Session réinitialisée !")

credits_service = CreditsService()
