import sqlite3

# --- PARAMÈTRES ---
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

# 1. LE DICTIONNAIRE DE L'HISTORIQUE DES CADEAUX
# Remplis cette liste avec les statistiques de tes meilleurs donateurs passés.
# Format : "pseudo_en_minuscule": nombre_de_cadeaux_offerts
HISTORIQUE_CADEAUX = {
    "yukino3032": 150,
    "un_autre_viewer": 50,
    "super_gifteuse": 25,
    # Ajoute les autres ici en respectant bien les virgules
}

def injecter_historique_cadeaux():
    print("🚀 Lancement de l'injection de l'historique des Subgifts...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        compteur = 0
        
        # 2. BOUCLE DE MISE À JOUR
        for pseudo, cadeaux in HISTORIQUE_CADEAUX.items():
            # On utilise une requête conditionnelle puissante :
            # Si le viewer n'existe pas, on le crée avec son nombre de cadeaux.
            # S'il existe déjà, on additionne ces cadeaux historiques à son compteur actuel.
            cursor.execute("""
                INSERT INTO viewers (twitch_id, username, gifts_count)
                VALUES (
                    COALESCE((SELECT twitch_id FROM viewers WHERE LOWER(username) = ?), 'inconnu_' || ?), 
                    ?, 
                    ?
                )
                ON CONFLICT(twitch_id) DO UPDATE SET
                    gifts_count = gifts_count + ?,
                    username = excluded.username
            """, (pseudo.lower(), pseudo.lower(), pseudo, cadeaux, cadeaux))
            
            print(f"🎁 {cadeaux} cadeaux historiques injectés pour le profil : {pseudo}")
            compteur += 1
            
        # 3. SAUVEGARDE
        conn.commit()
        print("-" * 50)
        print(f"✨ OPÉRATION TERMINÉE : L'historique de {compteur} profils a été restauré avec succès !")
        print("-" * 50)

    except Exception as e:
        print(f"❌ Erreur lors de l'injection : {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    injecter_historique_cadeaux()
