import requests

from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import APIException

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import MultiPartParser, FormParser

from dechets.models import TypeDechet

from .models import ScanDechet, AnalyseIA, DetectionIA
from .serializers import (
    ScanDechetSerializer,
    ScanDechetCreationSerializer
)


def analyser_photo_avec_ia(scan):
    """
    Envoie la photo du scan au microservice FastAPI
    afin qu'elle soit analysée par Gemini.
    """

    # Ouvre la photo enregistrée par Django.
    with scan.photoUrl.open('rb') as image:

        fichiers = {
            'photoUrl': (
                scan.photoUrl.name,
                image,
                'image/jpeg'
            )
        }

        # Appel du microservice IA.
        response = requests.post(
            f"{settings.IA_SERVICE_URL}/api/ia/analyse",
            files=fichiers,
            timeout=60
        )

    # Si FastAPI retourne une erreur.
    if response.status_code != 200:
        raise APIException(
            "Le service d'analyse IA est temporairement indisponible."
        )

    return response.json()


class ScanDechetCreateView(APIView):

    # Autorise les visiteurs non connectés à scanner.
    permission_classes = [AllowAny]

    # Nécessaire pour recevoir une photo.
    parser_classes = [MultiPartParser, FormParser]

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