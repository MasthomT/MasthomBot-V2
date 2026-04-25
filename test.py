import sqlite3
import os

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def activate_shields():
    print("="*60)
    print("🛡️ ACTIVATION DES BOUCLIERS ANTI-DOUBLONS ABSOLUS")
    print("="*60)

    if not os.path.exists(DB_PATH):
        print("❌ Base de données introuvable.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- 1. NETTOYAGE PRÉALABLE OBLIGATOIRE ---
    print("\n🧹 1. Désintégration des derniers doublons existants...")
    
    # Doublons Fil d'actu (On supprime l'excédent)
    cursor.execute("""
        DELETE FROM stream_events 
        WHERE id NOT IN (
            SELECT MIN(id) FROM stream_events
            GROUP BY event_type, LOWER(username), details, timestamp
        )
    """)
    print(f"   -> {cursor.rowcount} événements fantômes supprimés du Fil d'actualité.")

    # Doublons Viewers (Au cas où des comptes manuels auraient été recréés)
    cursor.execute("""
        DELETE FROM viewers 
        WHERE rowid NOT IN (
            SELECT MIN(rowid) FROM viewers
            GROUP BY LOWER(username)
        )
    """)
    print(f"   -> {cursor.rowcount} comptes clones supprimés du Classement.")

    # --- 2. ACTIVATION DES SÉCURITÉS PHYSIQUES (INDEX UNIQUE) ---
    print("\n🧱 2. Cimentation de la base de données...")
    
    try:
        # Règle 1 : Un pseudo ne peut exister qu'une seule fois (insensible à la majuscule)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS shield_unique_username ON viewers(username COLLATE NOCASE)")
        print("   ✅ Bouclier Viewers ACTIF : Impossible de créer un compte en double.")
    except Exception as e:
        print(f"   ❌ Erreur Bouclier Viewers : {e}")

    try:
        # Règle 2 : Un événement identique à la même seconde exacte est violemment rejeté
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS shield_unique_event ON stream_events(event_type, username, details, timestamp)")
        print("   ✅ Bouclier Événements ACTIF : Impossible de spammer le fil d'actualité.")
    except Exception as e:
        print(f"   ❌ Erreur Bouclier Événements : {e}")

    conn.commit()
    conn.close()
    
    print("\n" + "="*60)
    print("🎉 FÉLICITATIONS ! TA BASE DE DONNÉES EST DÉSORMAIS IMPÉNÉTRABLE.")
    print("Même si Twitch bégaye ou qu'un script fait une erreur, SQLite")
    print("bloquera l'insertion. Plus aucun doublon ne pourra s'afficher !")
    print("="*60)

if __name__ == "__main__":
    activate_shields()
