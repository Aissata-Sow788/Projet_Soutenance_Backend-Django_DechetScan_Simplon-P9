from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .models import PointCollecte
from .serializers import PointCollecteSerializer, PointCollecteEcritureSerializer


class PointCollecteViewSet(viewsets.ModelViewSet):
    queryset = PointCollecte.objects.filter(statut='actif')
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        # Lecture : affiche les types de déchets en entier
        # Écriture (creation/modification) : accepte juste une liste d'id
        if self.request.method in ['POST', 'PUT', 'PATCH']:
            return PointCollecteEcritureSerializer
        return PointCollecteSerializer

    def perform_create(self, serializer):
        # L'utilisateur connecté devient automatiquement le gérant du point créé
        serializer.save(gerePar=self.request.user)