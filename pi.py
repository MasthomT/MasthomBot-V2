import os
import glob

SERVICES_DIR = "/home/masthom/BOT_V2/app/services"

def cure_all():
    print("="*60)
    print("🏥 OPÉRATION DE GUÉRISON GLOBALE (RETRAIT DES TIMEOUTS)")
    print("="*60)

    patched_total = 0
    
    for filepath in glob.glob(f"{SERVICES_DIR}/*.py"):
        if not os.path.isfile(filepath): continue
        
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        modified = False
        for line in lines:
            # 1. On détruit la ligne qui déclare le timeout
            if "timeout = aiohttp.ClientTimeout" in line:
                modified = True
                continue
            
            # 2. On remet la session d'origine (infinie)
            if "async with aiohttp.ClientSession(timeout=timeout)" in line:
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}async with aiohttp.ClientSession() as session:\n")
                modified = True
            else:
                new_lines.append(line)

        # Si le fichier a été soigné, on le sauvegarde
        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print(f"✅ Guérison appliquée sur : {os.path.basename(filepath)}")
            patched_total += 1

    print(f"\n🎉 Terminé ! {patched_total} fichiers ont retrouvé leur pleine liberté.")

if __name__ == "__main__":
    cure_all()
