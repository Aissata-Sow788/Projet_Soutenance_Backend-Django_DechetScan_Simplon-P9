from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import MultiPartParser, FormParser

from .models import ScanDechet
from .serializers import (
    ScanDechetSerializer,
    ScanDechetCreationSerializer
)


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
            scan = serializer.save()

            # Rattache le scan à l'utilisateur seulement s'il est connecté
            if request.user.is_authenticated:
                scan.idUtilisateur = request.user
                scan.save()

            # Renvoie le scan avec le serializer de lecture (inclut analyseIA)
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