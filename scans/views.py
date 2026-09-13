from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import MultiPartParser, FormParser

from .models import ScanDechet
from .serializers import (
    ScanDechetSerializer,
    ScanDechetCreationSerializer
)


class ScanDechetCreateView(APIView):

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

            if request.user.is_authenticated:
                scan.idUtilisateur = request.user
                scan.save()

            return Response(
                ScanDechetSerializer(scan).data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class ScanDechetListView(APIView):

    @extend_schema(
        responses=ScanDechetSerializer(many=True)
    )
    def get(self, request):

        if not request.user.is_authenticated:
            return Response(
                [],
                status=status.HTTP_200_OK
            )

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