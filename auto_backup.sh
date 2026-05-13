#!/bin/bash

# Chemins
REPO_DIR="/home/thomas/masthom/BOT_V2"
DB_NAME="bot_database.db"
BACKUP_NAME="database_backup.sql"

echo "📦 Lancement de la sauvegarde automatique..."

# 1. Aller dans le dossier
cd $REPO_DIR

# 2. Créer l'export SQL (le dump)
# On utilise la commande .dump de sqlite3
sqlite3 $DB_NAME ".dump" > $BACKUP_NAME

# 3. Ajouter à Git
git add $BACKUP_NAME

# 4. Faire le commit avec la date du jour
git commit -m "Automated backup - $(date +'%Y-%m-%d %H:%M')"

# 5. Envoyer sur GitHub
# Note : il faut que ton Pi soit connecté en SSH ou ait mémorisé tes identifiants
git push origin main

echo "✅ Sauvegarde envoyée sur GitHub !"
