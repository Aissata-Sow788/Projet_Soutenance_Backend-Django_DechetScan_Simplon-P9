import requests
import mimetypes
import logging
from django.utils import timezone

from django.conf import settings
from users.permissions import IsAdmin
# Permet de faire les regroupements et les comptages SQL.
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import APIException
# Permet de compter les utilisateurs de ton modèle User.
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import MultiPartParser, FormParser

from dechets.models import PanierDechet, TypeDechet

from .models import ScanDechet, AnalyseIA, DetectionIA
from .serializers import (
    ScanDechetSerializer,
    ScanDechetCreationSerializer,
    ScanDechetAdminSerializer
)
from collecte.models import PointCollecte
from notifications.services import creer_notification_apres_scan


logger = logging.getLogger(__name__)


class IAServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "Le service d’analyse est temporairement indisponible. "
        "Veuillez réessayer dans quelques instants."
    )
    default_code = 'ia_service_unavailable'


def analyser_fichier_avec_ia(fichier):
    """
    Envoie directement un fichier à FastAPI sans obliger Django
    à créer préalablement un objet ScanDechet en base de données.
    """

    # URL du microservice IA.
    url = f"{settings.IA_SERVICE_URL}/api/ia/analyse"

    # Détermine le type MIME du fichier envoyé.
    mime_type = (
        mimetypes.guess_type(fichier.name)[0]
        or "image/jpeg"
    )

    try:
        # Revenir au début du fichier avant de l'envoyer.
        fichier.seek(0)

        # Envoyer l'image au microservice FastAPI.
        response = requests.post(
            url,
            files={
                "photoUrl": (
                    fichier.name,
                    fichier,
                    mime_type,
                )
            },
            timeout=60,
        )

        # Signaler les erreurs du microservice.
        if response.status_code != 200:
            logger.error(
                "Erreur du microservice IA : HTTP %s - %s",
                response.status_code,
                response.text,
            )

        response.raise_for_status()

        # Retourner les détections produites par l'IA.
        return response.json()

    finally:
        # Réinitialiser le fichier pour permettre son enregistrement
        # ultérieur si le citoyen est connecté.
        fichier.seek(0)

def analyser_photo_avec_ia(scan):
    """
    Envoie la photo enregistrée par Django au microservice IA
    pour qu'elle soit analysée par Gemini.
    """

    # URL du microservice FastAPI.
    # On lit depuis settings.IA_SERVICE_URL qui vient de la variable
    # d'environnement IA_SERVICE_URL.
    # En local  : http://127.0.0.1:8001
    # En Docker : http://ia-service:8001  (nom du service docker-compose)
    url = f"{settings.IA_SERVICE_URL}/api/ia/analyse"

    # Détermine automatiquement le type MIME de l'image.
    # Exemple : .jpg -> image/jpeg, .png -> image/png.
    mime_type = mimetypes.guess_type(
        scan.photoUrl.name
    )[0] or "image/jpeg"

    # Ouvre l'image enregistrée par Django en lecture binaire.
    with scan.photoUrl.open("rb") as image:

        # Envoie l'image à FastAPI.
        # IMPORTANT : FastAPI attend précisément le champ "photoUrl".
        response = requests.post(
            url,
            files={
                "photoUrl": (
                    scan.photoUrl.name,
                    image,
                    mime_type,
                )
            },

            # Laisse suffisamment de temps à Gemini pour effectuer
            # l'analyse et ses éventuelles tentatives supplémentaires.
            timeout=60,
        )

    # Si FastAPI retourne une erreur HTTP, elle sera signalée ici.
    if response.status_code != 200:
        print("========================================")
        print("ERREUR MICRO-SERVICE IA")
        print("STATUS :", response.status_code)
        print("REPONSE :", response.text)
        print("========================================")

    # Déclenche l'exception si le statut HTTP est une erreur.
    response.raise_for_status()

    # Retourne le résultat JSON produit par FastAPI.
    return response.json()

class ScanDechetCreateView(APIView):

    # Les citoyens connectés et les visiteurs peuvent scanner.
    permission_classes = [AllowAny]

    # Autorise la réception des photos envoyées par Angular.
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request=ScanDechetCreationSerializer,
        responses=ScanDechetSerializer,
    )
    def post(self, request):
        # Vérifier la photo sans enregistrer immédiatement un scan.
        serializer = ScanDechetCreationSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Récupérer la photo validée par le serializer.
        fichier = serializer.validated_data["photoUrl"]

        # -------------------------------------------------------
        # ÉTAPE 1 : ANALYSE IA
        # -------------------------------------------------------
        # L'image est envoyée directement à FastAPI.
        # Aucun ScanDechet n'est créé à cette étape.
        try:
            resultat_ia = analyser_fichier_avec_ia(fichier)

        except requests.RequestException as erreur:
            logger.exception(
                "Le microservice IA n'a pas pu analyser la photo."
            )
            raise IAServiceUnavailable() from erreur

        # -------------------------------------------------------
        # ÉTAPE 2 : CITOYEN ANONYME
        # -------------------------------------------------------
        # Ne créer aucun enregistrement en base de données.
        # Renvoyer directement le résultat de l'analyse à Angular.
        if not request.user.is_authenticated:

            # Préparer un résultat compatible avec la structure
            # générale utilisée par les pages de résultats.
            date_analyse = timezone.now()

            detections_anonymes = []

            for detection in resultat_ia.get("dechets", []):
                categorie = detection.get("categorie")

                # Lecture seule du référentiel Django :
                # aucune catégorie ni détection n'est créée ici.
                type_dechet = TypeDechet.objects.filter(
                    nom=categorie
                ).first()

                detections_anonymes.append({
                    "idDetection": None,
                    "objet": detection.get("objet"),
                    "confiance": detection.get("confiance"),
                    "idTypeDechet": (
                        {
                            "idTypeDechet": type_dechet.pk,
                            "nom": type_dechet.nom,
                            "description": type_dechet.description,
                        }
                        if type_dechet
                        else None
                    ),
                })

            return Response(
                {
                    "idScan": None,
                    "dateScan": date_analyse,
                    "photoUrl": None,
                    "idUtilisateur": None,
                    "analyseIA": {
                        "idAnalyse": None,
                        "dateAnalyse": date_analyse,
                        "detections": detections_anonymes,
                    },
                    "resultatIA": resultat_ia,
                    "messageRemerciement": "Merci pour votre scan !",
                },
                status=status.HTTP_200_OK,
            )

        # -------------------------------------------------------
        # ÉTAPE 3 : CITOYEN CONNECTÉ
        # -------------------------------------------------------
        # L'analyse a réussi : enregistrer maintenant le scan
        # en l'associant directement au citoyen authentifié.
        scan = serializer.save(
            idUtilisateur=request.user
        )

        # Créer l'analyse liée au scan enregistré.
        analyse = AnalyseIA.objects.create(
            idScan=scan
        )

        # Enregistrer les détections et initialiser les paniers
        # des catégories reconnues, comme dans ton code initial.
        for detection in resultat_ia.get("dechets", []):

            categorie = detection.get("categorie")
            objet = detection.get("objet")
            confiance = detection.get("confiance")

            type_dechet = TypeDechet.objects.filter(
                nom=categorie
            ).first()

            # Ignorer les catégories absentes du référentiel.
            if not type_dechet:
                continue

            DetectionIA.objects.create(
                objet=objet,
                confiance=confiance,
                idAnalyse=analyse,
                idTypeDechet=type_dechet,
            )

            # Initialiser le panier sans inventer de quantité.
            PanierDechet.objects.get_or_create(
                idUtilisateur=request.user,
                idTypeDechet=type_dechet,
                defaults={
                    "nombreDisponible": 0,
                    "unite": "objet",
                },
            )

        # La notification persistante concerne uniquement
        # le citoyen connecté.
        message_remerciement = "Merci pour votre scan !"

        creer_notification_apres_scan(
            scan,
            message_remerciement,
        )

        # Retourner la réponse habituelle de l'API.
        reponse = ScanDechetSerializer(scan).data
        reponse["messageRemerciement"] = message_remerciement

        return Response(
            reponse,
            status=status.HTTP_201_CREATED,
        )


class ScanDechetListView(APIView):

    # L'historique est accessible uniquement
    # à l'utilisateur connecté.
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=ScanDechetSerializer(many=True)
    )
    def get(self, request):

        # Récupère uniquement les scans de l'utilisateur connecté.
        scans = ScanDechet.objects.filter(
            idUtilisateur=request.user
        ).order_by('-dateScan')

        # Affiche les scans trouvés dans le terminal Django.
        print(
            "SCANS TROUVÉS :",
            list(
                scans.values(
                    'idScan',
                    'idUtilisateur',
                    'dateScan'
                )
            )
        )

        # Sérialise les scans.
        serializer = ScanDechetSerializer( scans, many=True)

        # Retourne l'historique.
        return Response(serializer.data, status=status.HTTP_200_OK)

class ScanDechetDetailView(APIView):
    # Permet à un utilisateur connecté ou non de consulter
    # le résultat d'un scan précis.
    permission_classes = [AllowAny]

    def get(self, request, idScan):
        try:
            # Recherche le scan correspondant à l'identifiant reçu
            # dans l'URL.
            scan = ScanDechet.objects.get(idScan=idScan)

        except ScanDechet.DoesNotExist:
            # Retourne une erreur claire si le scan n'existe pas.
            return Response(
                {'detail': 'Scan introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Sérialise le scan avec son AnalyseIA et ses détections.
        serializer = ScanDechetSerializer(scan)

        # Retourne toutes les données du scan.
        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


class ScanDechetAdminListView(APIView):

    # Les données administrateur sont réservées au rôle admin.
    permission_classes = [IsAdmin]

    def get(self, request):

        # ========================================================
        # INFORMATIONS SUR L'UTILISATEUR CONNECTÉ
        # ========================================================

        # Ces print permettent de vérifier dans le terminal Django
        # que le token JWT a bien été reçu et reconnu.
        print("================ SCANS ADMIN ================")
        print("Utilisateur :", request.user.email)
        print("Authentifié :", request.user.is_authenticated)
        print("ID utilisateur :", request.user.id)
        print("Rôle :", request.user.role)
        print("=============================================")

        # ========================================================
        # RÉCUPÉRATION DES SCANS
        # ========================================================

        # Récupère tous les scans avec leur utilisateur.
        # Les relations IA sont préchargées pour éviter
        # plusieurs requêtes SQL lors de la sérialisation.
        scans = (
            ScanDechet.objects
            .select_related('idUtilisateur')
            .prefetch_related(
                'analyseIA__detections__idTypeDechet'
            )
            .order_by('-dateScan')
        )

        # Affiche le nombre total de scans trouvés.
        print("NOMBRE DE SCANS :", scans.count())

        # ========================================================
        # SÉRIALISATION
        # ========================================================

        # Transforme les objets Django en données JSON
        # compréhensibles par Angular.
        serializer = ScanDechetAdminSerializer(
            scans,
            many=True,
            context={'request': request}
        )

        # Retourne les données au frontend Angular.
        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

class DashboardStatistiquesView(APIView):

    # Les statistiques détaillées sont réservées au rôle admin.
    permission_classes = [IsAdmin]

    def get(self, request):

        # ========================================================
        # STATISTIQUES GÉNÉRALES
        # ========================================================

        # Nombre total de scans enregistrés dans la base.
        nombre_scans = ScanDechet.objects.count()

        # Récupère le modèle utilisateur réellement utilisé
        # par ton projet Django.
        User = get_user_model()

        # Nombre total d'utilisateurs enregistrés.
        utilisateurs_actifs = User.objects.count()

        # Nombre de points de collecte actuellement actifs.
        points_actifs = PointCollecte.objects.filter(
            statut='actif'
        ).count()

        # ========================================================
        # DÉCHETS ANALYSÉS
        # ========================================================

        # Chaque DetectionIA correspond à un déchet identifié
        # par l'intelligence artificielle.
        dechets_analyses = DetectionIA.objects.count()

        # ========================================================
        # RÉPARTITION DES DÉCHETS
        # ========================================================

        # Regroupe les détections par type de déchet.
        repartition = DetectionIA.objects.values(
            'idTypeDechet__nom'
        ).annotate(
            total=Count('idDetection')
        )

        # Prépare un dictionnaire facilement exploitable
        # depuis Angular.
        repartition_dechets = {}

        for element in repartition:

            # Récupère le nom du type de déchet.
            nom = element['idTypeDechet__nom']

            # Récupère le nombre de détections.
            total = element['total']

            # Ajoute le résultat dans le dictionnaire.
            repartition_dechets[nom] = total

        # ========================================================
        # PARTICIPATION CITOYENNE
        # ========================================================

        # Nombre d'utilisateurs ayant réalisé au moins un scan.
        utilisateurs_ayant_scan = (
            ScanDechet.objects
            .filter(idUtilisateur__isnull=False)
            .values('idUtilisateur')
            .distinct()
            .count()
        )

        # Évite une division par zéro si aucun utilisateur
        # n'existe encore dans la base.
        if utilisateurs_actifs > 0:

            taux_participation = round(
                (
                    utilisateurs_ayant_scan
                    / utilisateurs_actifs
                ) * 100,
                1
            )

        else:
            taux_participation = 0

        # ========================================================
        # RÉPONSE DE L'API
        # ========================================================

        return Response({

            # Statistiques principales.
            'nombreScans': nombre_scans,
            'utilisateursActifs': utilisateurs_actifs,
            'pointsActifs': points_actifs,
            'dechetsAnalyses': dechets_analyses,

            # Statistiques de participation.
            'utilisateursAyantScan': utilisateurs_ayant_scan,
            'tauxParticipation': taux_participation,

            # Répartition par catégorie.
            'repartitionDechets': repartition_dechets,

        })

class StatsAccueilPublicView(APIView):
    """
    Endpoint PUBLIC — accessible sans token JWT.
    Retourne uniquement les statistiques nécessaires
    à la page d'accueil pour les visiteurs non connectés :
    - nombre total de scans
    - nombre total d'utilisateurs
    Ces données sont inoffensives à exposer publiquement.
    """

    # Accessible à tous — utilisateurs connectés ou non.
    permission_classes = [AllowAny]

    def get(self, request):

        # Nombre total de scans enregistrés en base.
        nombre_scans = ScanDechet.objects.count()

        # Nombre total d'utilisateurs enregistrés.
        User = get_user_model()
        nombre_utilisateurs = User.objects.count()

        return Response({
            'nombreScans':       nombre_scans,
            'nombreUtilisateurs': nombre_utilisateurs,
        })


# ============================================================
# DÉTAIL D'UN SCAN POUR L'ADMINISTRATEUR
# ============================================================

class ScanDechetAdminDetailView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, idScan):
        try:
            scan = (
                ScanDechet.objects
                .select_related('idUtilisateur')
                .prefetch_related(
                    'analyseIA__detections__idTypeDechet'
                )
                .get(idScan=idScan)
            )

        except ScanDechet.DoesNotExist:
            return Response(
                {'detail': 'Scan introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ScanDechetAdminSerializer(
            scan,
            context={'request': request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )