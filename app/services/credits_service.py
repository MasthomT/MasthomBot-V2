import logging
import json
import os

logger = logging.getLogger("masthbot.credits")
SESSION_FILE = "/home/masthom/BOT_V2/credits_session.json"

class CreditsService:
    def __init__(self):
        self.session_watchtime = {}
        self.session_messages = {}
        # Les catégories spécifiques (Actions)
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
            except: pass

    def _save_session(self):
        try:
            data = {"session_watchtime": self.session_watchtime, "session_messages": self.session_messages, "categories": self.categories, "config": self.config}
            with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except: pass

    def add_watchtime(self, name, minutes=1):
        n = name.lower()
        self.session_watchtime[n] = self.session_watchtime.get(n, 0) + minutes
        self._save_session()

    def log_event(self, category, name, label=""):
        if category not in self.categories and category != "viewers": return
        n = name.lower()
        if category in ["chatters", "moderators", "vips"]:
            self.session_messages[n] = self.session_messages.get(n, 0) + 1
        
        if category != "viewers":
            self.categories[category][n] = {"name": name, "label": label}
            
        # ✅ LE FIX ABSOLU EST ICI : 
        # Si quelqu'un déclenche un event (sub, vip, mod, chatter...)
        # On l'injecte immédiatement dans le watchtime avec 0 min (s'il n'y est pas déjà).
        # Il apparaîtra donc FORCÉMENT dans la catégorie Viewers à la fin !
        if n not in self.session_watchtime:
            self.session_watchtime[n] = 0

        self._save_session()

    def get_stats(self):
        """Prépare les listes pour l'overlay OBS."""
        data = {}

        # 1. On traite les catégories d'actions (Subs, Modos, etc.)
        for cat, users in self.categories.items():
            cat_list = []
            for n, info in users.items():
                final_label = info["label"]
                if cat in ["chatters", "moderators", "vips"]:
                    msg_count = self.session_messages.get(n, 1)
                    final_label = f"{final_label} • 💬 {msg_count} msg" if final_label else f"💬 {msg_count} msg"
                cat_list.append({"name": info["name"], "label": final_label})
            data[cat] = sorted(cat_list, key=lambda x: x["name"].lower())

        # 2. ✅ LA CATÉGORIE VIEWERS (LISTE GLOBALE DE TOUS CEUX QUI ONT INTERAGI)
        viewers_list = []
        for n, minutes in self.session_watchtime.items():
            # On cherche le vrai nom (avec majuscules) dans les autres tables
            display_name = n.capitalize()
            for cat in self.categories:
                if n in self.categories[cat]:
                    display_name = self.categories[cat][n]["name"]
                    break
            
            wt_str = f"{minutes} min" if minutes < 60 else f"{minutes//60}h{minutes%60:02d}"
            viewers_list.append({
                "name": display_name,
                "label": f"⏱️ {wt_str}"
            })
        
        data["viewers"] = sorted(viewers_list, key=lambda x: x["name"].lower())
        return data

    def reset_session(self):
        self.session_watchtime = {}
        self.session_messages = {}
        for cat in self.categories: self.categories[cat] = {}
        self._save_session()

credits_service = CreditsService()
