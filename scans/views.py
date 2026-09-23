import requests
import mimetypes

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

from dechets.models import TypeDechet

from .models import ScanDechet, AnalyseIA, DetectionIA
from .serializers import (
    ScanDechetSerializer,
    ScanDechetCreationSerializer,
    ScanDechetAdminSerializer
)
from collecte.models import PointCollecte


def analyser_photo_avec_ia(scan):
    """
    Envoie la photo enregistrée par Django au microservice IA
    pour qu'elle soit analysée par Gemini.
    """

    # URL du microservice FastAPI.
    url = "http://127.0.0.1:8001/api/ia/analyse"

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
            timeout=180,
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

    # Autorise les visiteurs non connectés à scanner.
    permission_classes = [AllowAny]

    # Nécessaire pour recevoir une photo.
    parser_classes = [MultiPartParser, FormParser]

    # Cette partie sert à décrire ton endpoint dans Swagger/OpenAPI.
    @extend_schema(
        request=ScanDechetCreationSerializer,
        responses=ScanDechetSerializer
    )

    def post(self, request):

        # Vérifie les données envoyées par Angular.
        serializer = ScanDechetCreationSerializer(
            data=request.data
        )

        if serializer.is_valid():

            # Enregistre la photo du scan.
            scan = serializer.save()

            #  Rattache le scan à l'utilisateur
            # uniquement s'il est connecté.
            if request.user.is_authenticated:
                scan.idUtilisateur = request.user
                scan.save()

            # Envoie la photo au microservice IA.
            resultat_ia = analyser_photo_avec_ia(scan)

            # Crée l'analyse IA liée au scan.
            analyse = AnalyseIA.objects.create(
                idScan=scan
            )

            # Parcourt les déchets détectés par Gemini.
            for detection in resultat_ia.get('dechets', []):

                categorie = detection.get('categorie')
                objet = detection.get('objet')
                confiance = detection.get('confiance')

                # Recherche la catégorie dans
                # le référentiel officiel Django.
                type_dechet = TypeDechet.objects.filter(
                    nom=categorie
                ).first()

                # Si la catégorie n'existe pas,
                # on ignore cette détection.
                if not type_dechet:
                    continue

                # Enregistre la détection.
                DetectionIA.objects.create(
                    objet=objet,
                    confiance=confiance,
                    idAnalyse=analyse,
                    idTypeDechet=type_dechet
                )

            # Prépare les données pour n8n.
            donnees_n8n = {
                'idScan': scan.idScan,
                'message': 'Merci pour votre scan !'
            }

            try:
                # Appelle le Webhook n8n.
                response_n8n = requests.post(
                    'http://localhost:5678/webhook/dechetscan/scan',
                    json=donnees_n8n,
                    timeout=5
                )

                # Affiche la réponse n8n dans le terminal.
                print(
                    'Réponse n8n :',
                    response_n8n.status_code,
                    response_n8n.text
                )

            except requests.RequestException as erreur:

                # Une erreur n8n ne doit pas empêcher
                # le scan et l'analyse IA de fonctionner.
                print(
                    "Erreur lors de l'appel du Webhook n8n :",
                    erreur
                )

            # 10. Renvoie le scan avec son analyse,
            # ses détections et les conseils de tri.
            return Response(ScanDechetSerializer(scan).data, status=status.HTTP_201_CREATED)

        # Retourne les erreurs si la photo est invalide.
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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

    # Seuls les utilisateurs connectés peuvent accéder
    # à la liste des scans administrateur.
    permission_classes = [IsAuthenticated]

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

    # Seuls les utilisateurs connectés peuvent consulter
    # les statistiques du tableau de bord.
    permission_classes = [IsAuthenticated]

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

# ============================================================
# DÉTAIL D'UN SCAN POUR L'ADMINISTRATEUR
# ============================================================

class ScanDechetAdminDetailView(APIView):
    permission_classes = [IsAuthenticated]

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