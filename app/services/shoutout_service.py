import requests
import sqlite3
import os

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"
NODE_URL = "http://192.168.1.109:3005" # Ton IP locale pour le Node

class ShoutoutService:
    # --- LA FONCTION QU'IL MANQUAIT ---
    def get_config(self):
        """Récupère la config pour le Node.js depuis la base de données"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM settings LIMIT 1").fetchone()
            conn.close()
            return dict(row) if row else {}
        except Exception as e:
            print(f"❌ [DB Error] Impossible de lire la config: {e}")
            return {}

    # --- LES FONCTIONS DE DECLENCHEMENT ---
    def trigger_replay(self, slug=None, query=None):
        """Envoie l'ordre de replay au serveur Node.js"""
        payload = {"slug": slug, "query": query}
        try:
            requests.post(f"{NODE_URL}/api/replay", json=payload, timeout=2)
            return True
        except Exception as e:
            print(f"❌ [Node Replay Error] : {e}")
            return False

    def trigger_shoutout(self, target, slug=None, duration=30):
        """Envoie l'ordre de Shoutout au serveur Node.js"""
        payload = {
            "target": target,
            "slug": slug,
            "duration": duration
        }
        try:
            requests.post(f"{NODE_URL}/api/shoutout", json=payload, timeout=2)
            return True
        except Exception as e:
            print(f"❌ [Node SO Error] : {e}")
            return False

shoutout_service = ShoutoutService()
