import sqlite3
import os

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def remove_viewer(target_username):
    print("="*50)
    print(f"🗑️ PROTOCOLE D'EFFACEMENT POUR : {target_username.upper()}")
    print("="*50)

    if not os.path.exists(DB_PATH):
        print(f"❌ ERREUR : Base de données introuvable à {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. On cherche son ID Twitch pour tout nettoyer proprement
    row = cursor.execute("SELECT twitch_id, points FROM viewers WHERE LOWER(username) = ?", (target_username.lower(),)).fetchone()
    
    if not row:
        print(f"🤷‍♂️ Cible non trouvée. '{target_username}' n'est pas (ou plus) dans la base de données.")
        conn.close()
        return

    t_id = row[0]
    pts = row[1]
    print(f"🎯 Cible verrouillée ! (ID: {t_id} | EXP: {pts})")

    # 2. On supprime toutes ses traces dans TOUTES les tables
    tables = [
        "viewers",
        "viewer_exp_log",
        "viewer_daily_stats",
        "poll_votes",
        "questions"
    ]

    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table} WHERE twitch_id = ?", (t_id,))
            print(f"   🧹 Traces effacées de la table '{table}'")
        except sqlite3.OperationalError:
            pass # Si une table n'existe pas, on ignore silencieusement

    conn.commit()
    conn.close()
    
    print("\n✅ EXTERMINATION RÉUSSIE !")
    print(f"Le viewer '{target_username}' a totalement disparu du classement et de l'histoire.")
    print("="*50)

if __name__ == "__main__":
    # Tu peux changer le pseudo ici si tu as besoin de virer quelqu'un d'autre plus tard
    remove_viewer("dicoh06")
