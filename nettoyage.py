import os

def get_size_format(b, factor=1024, suffix="o"):
    """Formate la taille en Ko, Mo, Go"""
    for unit in ["", "K", "M", "G", "T"]:
        if b < factor:
            return f"{b:.2f} {unit}{suffix}"
        b /= factor
    return f"{b:.2f} P{suffix}"

def get_dir_size(start_path):
    """Calcule le poids total d'un dossier"""
    total_size = 0
    for dirpath, _, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def clean_old_system():
    print("="*60)
    print("🧹 DÉBUT DU GRAND MÉNAGE DE PRINTEMPS...")
    print("="*60)
    
    # 1. SUPPRESSION DE L'ANCIENNE BASE
    old_db = "/home/masthom/database.db"
    if os.path.exists(old_db):
        size = os.path.getsize(old_db)
        os.remove(old_db)
        print(f"✅ Ancienne base de données pulvérisée ! ({get_size_format(size)} libérés)")
    else:
        print("✅ Ancienne base de données déjà absente.")

    # 2. RECHERCHE DE L'ANCIEN DOSSIER FLASK
    print("\n🔍 Analyse de ton Raspberry Pi à la recherche de l'ancien bot...")
    home_dir = "/home/masthom"
    
    # On ignore BOT_V2 et les dossiers systèmes cachés
    safe_dirs = ["BOT_V2", ".cache", ".config", ".local", ".npm", ".pm2", ".ssh"]
    
    found_suspects = False
    for item in os.listdir(home_dir):
        path = os.path.join(home_dir, item)
        if os.path.isdir(path) and item not in safe_dirs and not item.startswith("."):
            try:
                size = get_dir_size(path)
                print(f"\n   👉 Ancien dossier détecté : {item}/ ({get_size_format(size)})")
                print(f"      ⚠️ Pour l'effacer DÉFINITIVEMENT, copie-colle cette commande :")
                print(f"      rm -rf {path}")
                found_suspects = True
            except Exception:
                pass

    if not found_suspects:
        print("\n   ✨ Aucun autre dossier suspect trouvé.")

    print("\n" + "="*60)
    print("🐾 FÉLIX V2 EST MAINTENANT LE SEUL MAÎTRE À BORD !")
    print("="*60)

if __name__ == "__main__":
    clean_old_system()
