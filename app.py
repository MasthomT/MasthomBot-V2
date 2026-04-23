import sqlite3

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

print("\n🔍 --- VÉRIFICATION DE LA BDD DES ANNONCES ---")
try:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    annonces = conn.execute("SELECT * FROM announcements").fetchall()
    print(f"📊 Nombre d'annonces trouvées : {len(annonces)}\n")
    
    if len(annonces) == 0:
        print("❌ LE BUG EST ICI : Ta base de données est vide !")
        print("💡 Solution : Va sur ta page Web (/admin/announcements), crée une annonce et clique sur Sauvegarder.")
    else:
        for a in annonces:
            print(f"🔸 ID {a['id']} : {a['label']}")
            print(f"   - Message : {a['message_template']}")
            print(f"   - Délai   : {a['interval_minutes']} minutes")
            print(f"   - Active  : {'OUI' if a['is_enabled'] else 'NON'}")
            print(f"   - Dernier : {a['last_triggered'] if a['last_triggered'] else 'JAMAIS'}")
            print("-" * 30)
        print("✅ LA BDD EST BONNE. Le problème vient du bot Twitch.")
        
except Exception as e:
    print(f"❌ ERREUR LECTURE BDD : {e}")
finally:
    conn.close()
