import os
import sys

print("🔍 Analyse de l'architecture des dossiers en cours...\n")

# 1. On définit le dossier racine (BOT_V2) et on l'ajoute au chemin Python
racine = os.path.dirname(os.path.abspath(__file__))
sys.path.append(racine)

# 2. Le "Détective" : On définit le chemin exact attendu pour label_service.py
chemin_attendu = os.path.join(racine, "app", "services", "label_service.py")

# 3. Vérification de la présence du fichier
if not os.path.exists(chemin_attendu):
    print("❌ ERREUR : Python ne trouve pas ton fichier de service.")
    print("👉 Il s'attend à le trouver exactement ici :")
    print(f"   {chemin_attendu}")
    print("\n💡 Que faire ?")
    print(" - Vérifie que tu as bien créé le fichier dans ce dossier précis.")
    print(" - Vérifie que le nom est bien en minuscules : 'label_service.py'.")
    print(" - Vérifie que l'extension est bien '.py' (et non '.txt').")
    sys.exit(1) # On arrête le script ici pour éviter le crash illisible

print("✅ Fichier 'label_service.py' détecté avec succès !")
print("🚀 Lancement de la simulation des Stream Labels...\n")

# Si on arrive ici, l'importation fonctionnera parfaitement
from app.services.label_service import write_label

def simuler_evenements():
    """Simule l'arrivée d'événements Twitch en écrivant des données de test."""
    
    print("👉 Simulation Follow : Moustachu_")
    write_label("dernier_follow.txt", "Moustachu_")

    print("👉 Simulation Sub : Bakataii (17 mois)")
    write_label("dernier_sub.txt", "Bakataii | 17 mois")

    print("👉 Simulation Subgift : Yukino3032 (1 subgift)")
    write_label("dernier_subgift.txt", "Yukino3032 | 1 subs")

    print("👉 Simulation Bits : Vestale7 (3 bits)")
    write_label("dernier_bits.txt", "Vestale7 | 3 bits")

    print("👉 Simulation Raid : Ponpon633 (9 raideurs)")
    write_label("dernier_raid.txt", "Ponpon633 | 9 viewers")

    print("\n✅ Simulation terminée avec succès !")

if __name__ == "__main__":
    simuler_evenements()
