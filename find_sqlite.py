import os

# Les mots-clés qui trahissent la présence de SQLite
KEYWORDS = ["sqlite3", "sqlite", ".db", "bot_database.db"]
FOUND = False

print("🔍 SCAN GLOBAL : Recherche des vestiges de SQLite en cours...\n")

for root, dirs, files in os.walk("."):
    # On ignore les dossiers système, git et l'environnement virtuel
    if any(p in root for p in ["venv", ".git", "__pycache__", ".pytest_cache"]):
        continue
        
    for file in files:
        # On ne scanne que le code source
        if file.endswith(".py") or file.endswith(".html") or file.endswith(".js"):
            file_path = os.path.join(root, file)
            
            # On évite que ce script se détecte lui-même
            if "find_sqlite.py" in file_path:
                continue
                
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line_num, line in enumerate(lines, 1):
                        line_lower = line.lower()
                        for kw in KEYWORDS:
                            if kw in line_lower:
                                # Sécurité pour ne pas remonter les commentaires d'exclusion si tu en as
                                print(f"❌ TROUVÉ -> Fichier : \033[93m{file_path}\033[0m (Ligne {line_num})")
                                print(f"   └── Code : \033[90m{line.strip()}\033[0m\n")
                                FOUND = True
                                break
            except Exception:
                pass

if not FOUND:
    print("🎉 INCROYABLE ! Plus aucune trace de SQLite ou de fichier .db dans ton code source !")
else:
    print("⚠️ Modifie ces fichiers pour remplacer l'import sqlite3 par get_db_connection() comme on l'a fait pour les autres.")
