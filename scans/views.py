import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import MultiPartParser, FormParser

from .models import ScanDechet
from .serializers import (ScanDechetSerializer, ScanDechetCreationSerializer)


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
        # Vérifie et enregistre la photo envoyée par Angular.
        serializer = ScanDechetCreationSerializer(
            data=request.data
        )

        if serializer.is_valid():
            # Enregistre le scan dans la base de données.
            scan = serializer.save()

            # Rattache le scan à l'utilisateur seulement s'il est connecté.
            if request.user.is_authenticated:
                scan.idUtilisateur = request.user
                scan.save()

                # Prépare les données qui seront envoyées à n8n.
                donnees_n8n = {
                    'idScan': scan.idScan,
                    'message': 'Merci pour votre scan !'
                }

                try:
                    # Appelle le Webhook n8n après la création du scan.
                    # Cette URL est l'URL de production du Webhook.
                    response_n8n = requests.post(
                        'http://localhost:5678/webhook/dechetscan/scan',
                        json=donnees_n8n,
                        timeout=5
                    )

                    # Affiche le résultat de l'appel n8n
                    # dans le terminal Django pour faciliter les tests.
                    print(
                        'Réponse n8n :',
                        response_n8n.status_code,
                        response_n8n.text
                    )

                except requests.RequestException as erreur:
                    # Une erreur n8n ne doit pas empêcher
                    # l'enregistrement du scan dans Django.
                    print(
                        'Erreur lors de l appel du Webhook n8n :',
                        erreur
                    )

            # Renvoie le scan avec le serializer de lecture
            # qui inclut notamment analyseIA.
            return Response(
                ScanDechetSerializer(scan).data,
                status=status.HTTP_201_CREATED
            )

        # Retourne les erreurs si les données du scan sont invalides.
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

class ScanDechetListView(APIView):

    # L'historique est personnel :
    # l'utilisateur doit donc être connecté avec un JWT valide.
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=ScanDechetSerializer(many=True)
    )
    def get(self, request):

        # Si aucun utilisateur n'est authentifié, retourne une liste vide.
        if not request.user.is_authenticated:
            return Response([], status=status.HTTP_200_OK)

        # Récupère uniquement les scans appartenant à cet utilisateur.
        scans = ScanDechet.objects.filter(idUtilisateur=request.user).order_by('-dateScan')

        # Affiche les scans trouvés dans le terminal Django.
        print("SCANS TROUVÉS :", list(
            scans.values('idScan', 'idUtilisateur', 'dateScan')
        ))

        # Sérialise les scans.
        serializer = ScanDechetSerializer(scans, many=True)

        # Retourne les données à Angular.
        return Response(serializer.data, status=status.HTTP_200_OK)
