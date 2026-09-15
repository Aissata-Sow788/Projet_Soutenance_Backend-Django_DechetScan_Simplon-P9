from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import TypeDechet, ConseilTri
from .serializers import TypeDechetSerializer, ConseilTriSerializer
from users.permissions import IsAdmin
from drf_spectacular.utils import extend_schema


class TypeDechetViewSet(viewsets.ModelViewSet):
    queryset = TypeDechet.objects.all()
    serializer_class = TypeDechetSerializer

    def get_permissions(self):
        # Lecture ouverte à tous (connectés ou non), écriture réservée aux admins
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticatedOrReadOnly()]

        return [IsAdmin()]


class ConseilTriViewSet(viewsets.ModelViewSet):
    queryset = ConseilTri.objects.all()
    serializer_class = ConseilTriSerializer

    def get_permissions(self):
        # Même logique que TypeDechet : seul un admin peut créer/modifier un conseil
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticatedOrReadOnly()]

        return [IsAdmin()]