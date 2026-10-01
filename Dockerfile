# =============================================================
# DOCKERFILE — Backend Django (DechetScan)
# =============================================================
# Un Dockerfile est une recette qui explique à Docker comment
# construire une "image" (une boîte autonome) contenant ton
# application et tout ce dont elle a besoin pour fonctionner.
# =============================================================


# -------------------------------------------------------------
# ÉTAPE 1 : Image de base
# -------------------------------------------------------------
# "FROM" définit le point de départ de notre image.
# On utilise Python 3.12 dans sa version "slim" (allégée)
# pour réduire la taille finale de l'image.
# -------------------------------------------------------------
FROM python:3.12-slim


# -------------------------------------------------------------
# ÉTAPE 2 : Variables d'environnement système
# -------------------------------------------------------------
# PYTHONDONTWRITEBYTECODE=1 → Python ne crée pas de fichiers
#   .pyc (bytecode compilé) inutiles dans le conteneur.
# PYTHONUNBUFFERED=1 → Les logs Python s'affichent en temps
#   réel dans le terminal Docker (sans mise en tampon).
# -------------------------------------------------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


# -------------------------------------------------------------
# ÉTAPE 3 : Dépendances système
# -------------------------------------------------------------
# Django avec MySQL nécessite le client C de MySQL (mysqlclient).
# On installe les bibliothèques système nécessaires via apt-get.
#   - pkg-config         : outil de configuration de compilation
#   - default-libmysqlclient-dev : headers MySQL pour compiler mysqlclient
#   - build-essential    : compilateur C/C++ (gcc, make...)
# On nettoie ensuite le cache apt pour alléger l'image.
# -------------------------------------------------------------
RUN apt-get update && apt-get install -y \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


# -------------------------------------------------------------
# ÉTAPE 4 : Répertoire de travail
# -------------------------------------------------------------
# "WORKDIR" définit le dossier courant à l'intérieur du
# conteneur. Toutes les commandes suivantes s'exécuteront
# depuis ce dossier /app.
# -------------------------------------------------------------
WORKDIR /app


# -------------------------------------------------------------
# ÉTAPE 5 : Installation des dépendances Python
# -------------------------------------------------------------
# On copie d'abord UNIQUEMENT requirements.txt (avant le reste
# du code) pour profiter du cache Docker : si le code change
# mais pas requirements.txt, Docker ne réinstalle pas tout.
# "pip install --no-cache-dir" évite de stocker le cache pip
# dans l'image, ce qui la garde légère.
# -------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# -------------------------------------------------------------
# ÉTAPE 6 : Copie du code source
# -------------------------------------------------------------
# On copie tout le code du backend dans /app du conteneur.
# Le .dockerignore (fichier séparé) exclut venv/, __pycache__/,
# .git/ etc. pour ne pas alourdir l'image.
# -------------------------------------------------------------
COPY . .


# -------------------------------------------------------------
# ÉTAPE 7 : Port exposé
# -------------------------------------------------------------
# "EXPOSE" documente que le conteneur écoute sur le port 8000.
# C'est informatif — le port réel est défini dans docker-compose.
# -------------------------------------------------------------
EXPOSE 8000


# -------------------------------------------------------------
# ÉTAPE 8 : Script de démarrage
# -------------------------------------------------------------
# On copie et rend exécutable un script entrypoint.sh qui :
#   1. Attend que MySQL soit prêt
#   2. Applique les migrations Django (python manage.py migrate)
#   3. Lance le serveur Gunicorn (serveur Python de production)
# -------------------------------------------------------------
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh


# -------------------------------------------------------------
# ÉTAPE 9 : Commande de lancement
# -------------------------------------------------------------
# "CMD" définit la commande exécutée au démarrage du conteneur.
# Ici on appelle notre script entrypoint.sh.
# -------------------------------------------------------------
CMD ["/entrypoint.sh"]
