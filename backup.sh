#!/bin/bash

# Configuration
DB_NAME="masthbot_db"
DB_USER="thomas"
BACKUP_DIR="/home/thomas/masthom/backups"
DATE=$(date +%Y-%m-%d_%Hh%M)

# 1. Sauvegarde propre et compressée de PostgreSQL
pg_dump -U $DB_USER -d $DB_NAME -F c -b -v -f "$BACKUP_DIR/postgres_backup_$DATE.dump"

# 2. Sécurité : On supprime les sauvegardes vieilles de plus de 7 jours
find "$BACKUP_DIR" -name "postgres_backup_*.dump" -mtime +7 -delete
