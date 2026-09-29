from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import TypeDechet, ConseilTri, PrixDechet
from .serializers import TypeDechetSerializer, ConseilTriSerializer, PrixDechetSerializer
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


class PrixDechetViewSet(viewsets.ModelViewSet):
    """
    CRUD complet pour les tarifs d'achat des déchets.
    - Lecture : tous les utilisateurs connectés peuvent consulter les prix.
    - Écriture : réservée aux administrateurs.
    """

    queryset = PrixDechet.objects.select_related('idTypeDechet').all()
    serializer_class = PrixDechetSerializer

    def get_permissions(self):
        # Lecture accessible à tous les utilisateurs connectés.
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticatedOrReadOnly()]

        # Création, modification et suppression réservées aux admins.
        return [IsAdmin()]