# 1. On part d'un système Linux ultra-léger avec Python 3.11 pré-installé
FROM python:3.11-slim

# 2. On définit le dossier de travail à l'intérieur de la "boîte"
WORKDIR /app

# 3. On installe les outils de base, Curl, ET Node.js 20 !
RUN apt-get update && \
    apt-get install -y gcc sqlite3 tzdata curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# 4. On règle le fuseau horaire sur Paris
ENV TZ=Europe/Paris

# 5. On copie ton fichier de dépendances Python et on les installe
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. On copie tout le reste de ton code
COPY . .

# 7. On installe les librairies Node.js nécessaires pour ton server.js
RUN npm install express cors || true

# 8. On indique que le bot communiquera sur les ports 8000 (Python) et 3005 (Node.js)
EXPOSE 8000
EXPOSE 3005

# 9. La commande de démarrage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
