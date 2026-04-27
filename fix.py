import os
import glob

SERVICES_DIR = "/home/masthom/BOT_V2/app/services"

def patch_timeouts():
    print("="*50)
    print("🛡️ DÉPLOIEMENT DU BOUCLIER ANTI-CRASH (TIMEOUTS)")
    print("="*50)

    patched_total = 0
    
    # On scanne tous les services vitaux de Félix (Twitch, EventSub, Modération...)
    for filepath in glob.glob(f"{SERVICES_DIR}/*.py"):
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        patched_file = 0
        
        for line in lines:
            # Si on détecte une requête sans limite de temps
            if "async with aiohttp.ClientSession() as session:" in line:
                # On copie l'indentation exacte (les espaces avant le texte) pour ne pas casser Python
                indent = line[:len(line) - len(line.lstrip())]
                
                # On injecte la limite stricte de 3 secondes
                new_lines.append(f"{indent}timeout = aiohttp.ClientTimeout(total=3)\n")
                new_lines.append(f"{indent}async with aiohttp.ClientSession(timeout=timeout) as session:\n")
                
                patched_file += 1
                patched_total += 1
            else:
                new_lines.append(line)

        # Si des modifications ont été faites, on sauvegarde le fichier
        if patched_file > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print(f"🔧 {patched_file} sécurités ajoutées dans : {os.path.basename(filepath)}")

    if patched_total > 0:
        print("\n✅ OPÉRATION RÉUSSIE !")
        print(f"Félix ne restera plus jamais bloqué dans le vide ({patched_total} requêtes sécurisées).")
        print("👉 Tape 'rebootbot' dans ton terminal pour appliquer la mise à jour.")
    else:
        print("⚠️ Le patch est déjà appliqué partout ! Félix est déjà protégé.")

if __name__ == "__main__":
    patch_timeouts()
