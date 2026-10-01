#!/bin/sh
# =============================================================
# ENTRYPOINT.SH — Script de démarrage du backend Django
# =============================================================
# Ce script s'exécute à chaque démarrage du conteneur Django.
# Son rôle : s'assurer que MySQL est prêt AVANT de lancer Django,
# puis appliquer les migrations et démarrer le serveur.
# =============================================================


# -------------------------------------------------------------
# "set -e" : arrête le script immédiatement si une commande
# retourne une erreur. Évite des comportements imprévisibles.
# -------------------------------------------------------------
set -e


echo "Attente que MySQL soit prêt..."

# -------------------------------------------------------------
# Boucle d'attente MySQL
# -------------------------------------------------------------
# On tente de se connecter à MySQL en boucle jusqu'à succès.
# "python -c" exécute du Python inline pour tester la connexion.
# Si MySQL n'est pas encore prêt, on attend 2 secondes et
# on réessaie. C'est nécessaire car MySQL met quelques secondes
# à démarrer et Django échouerait sinon.
# -------------------------------------------------------------
until python -c "
import MySQLdb, os, sys
try:
    MySQLdb.connect(
        host=os.environ.get('MYSQL_HOST', 'mysql'),
        user=os.environ.get('MYSQL_USER', 'dechetscan_user'),
        passwd=os.environ.get('MYSQL_PASSWORD', ''),
        db=os.environ.get('MYSQL_DATABASE', 'dechetscan_project')
    )
    sys.exit(0)
except Exception:
    sys.exit(1)
"; do
    echo "   MySQL pas encore prêt, nouvelle tentative dans 2s..."
    sleep 2
done

echo "MySQL est prêt !"


# -------------------------------------------------------------
# Migrations Django
# -------------------------------------------------------------
# "python manage.py migrate" crée ou met à jour les tables
# de la base de données selon les modèles Django.
# "--noinput" évite toute question interactive.
# -------------------------------------------------------------
echo " Application des migrations Django..."
python manage.py migrate --noinput


# -------------------------------------------------------------
# Collecte des fichiers statiques
# -------------------------------------------------------------
# Django rassemble tous les fichiers CSS/JS/images dans un
# dossier unique pour que le serveur web puisse les servir.
# -------------------------------------------------------------
echo " Collecte des fichiers statiques..."
python manage.py collectstatic --noinput


# -------------------------------------------------------------
# Lancement du serveur Gunicorn
# -------------------------------------------------------------
# Gunicorn est un serveur Python de production (plus robuste
# que le serveur de développement de Django).
#   --bind 0.0.0.0:8000 → écoute sur tous les interfaces, port 8000
#   --workers 3         → 3 processus parallèles pour les requêtes
#   config.wsgi:application → point d'entrée WSGI de Django
# -------------------------------------------------------------
echo " Démarrage du serveur Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3
