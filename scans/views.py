import requests

from django.conf import settings
from rest_framework.exceptions import APIException
from dechets.models import TypeDechet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import MultiPartParser, FormParser

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

    # Autorise les visiteurs non connectés à scanner
    permission_classes = [AllowAny]
    # Nécessaire pour recevoir un fichier (photo) dans la requête
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request=ScanDechetCreationSerializer,
        responses=ScanDechetSerializer
    )

    def post(self, request):
        serializer = ScanDechetCreationSerializer(
            data=request.data
        )

        if serializer.is_valid():

            #  Enregistre la photo du scan.
            scan = serializer.save()

            # Rattache le scan à l'utilisateur s'il est connecté.
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

                #  Recherche la catégorie dans le référentiel Django.
                type_dechet = TypeDechet.objects.filter(
                    nom=categorie
                ).first()

                # Si la catégorie retournée par Gemini
                # n'existe pas dans notre référentiel,
                # on ne crée pas de détection incohérente.
                if not type_dechet:
                    continue

                # Crée la détection IA.
                DetectionIA.objects.create(
                    objet=objet,
                    confiance=confiance,
                    idAnalyse=analyse,
                    idTypeDechet=type_dechet
                )

            # Renvoie le scan avec son analyse et ses détections.
            return Response(
                ScanDechetSerializer(scan).data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class ScanDechetListView(APIView):

    # Autorise l'appel même sans connexion
    permission_classes = [AllowAny]

    @extend_schema(
        responses=ScanDechetSerializer(many=True)
    )
    def get(self, request):

        # Pas connecté = pas d'historique personnel à afficher
        if not request.user.is_authenticated:
            return Response(
                [],
                status=status.HTTP_200_OK
            )

        # Scans de l'utilisateur, les plus récents en premier
        scans = ScanDechet.objects.filter(
            idUtilisateur=request.user
        ).order_by('-dateScan')

        serializer = ScanDechetSerializer(
            scans,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )