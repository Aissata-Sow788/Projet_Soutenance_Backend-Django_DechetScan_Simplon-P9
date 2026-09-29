from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q

from users.permissions import IsAdmin
from collecteurs.models import Collecteur
from .models import PointCollecte, Collecte
from .serializers import (
    PointCollecteSerializer,
    PointCollecteEcritureSerializer,
    CollecteSerializer,
    CollecteCreationSerializer,
    CollecteStatutSerializer,
)


class PointCollecteViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        points = PointCollecte.objects.prefetch_related('dechetsAcceptes')
        utilisateur = self.request.user

        if self.action in ['update', 'partial_update', 'destroy']:
            if utilisateur.is_authenticated and utilisateur.role == 'admin':
                return points
            return points.filter(gerePar=utilisateur)

        if utilisateur.is_authenticated and utilisateur.role == 'admin':
            return points

        visibles = Q(statut='actif')
        if (
            utilisateur.is_authenticated
            and Collecteur.objects.filter(idUtilisateur=utilisateur).exists()
        ):
            visibles |= Q(gerePar=utilisateur)

        return points.filter(visibles).distinct()

    def get_serializer_class(self):
        # Lecture : affiche les types de déchets en entier
        # Écriture (creation/modification) : accepte juste une liste d'id
        if self.request.method in ['POST', 'PUT', 'PATCH']:
            return PointCollecteEcritureSerializer
        return PointCollecteSerializer

    def perform_create(self, serializer):
        utilisateur = self.request.user
        if (
            utilisateur.role != 'admin'
            and not Collecteur.objects.filter(idUtilisateur=utilisateur).exists()
        ):
            raise PermissionDenied(
                'Un profil collecteur est nécessaire pour créer un point de collecte.'
            )

        serializer.save(gerePar=self.request.user)


class CollecteViewSet(viewsets.ModelViewSet):
    """
    Endpoints pour la gestion des collectes réalisées par les collecteurs.

    - GET    /api/collectes/                 → admin: toutes les collectes
                                               collecteur: ses propres collectes
    - GET    /api/collectes/{id}/            → détail d'une collecte
    - POST   /api/collectes/                 → créer une collecte (collecteur connecté)
    - PATCH  /api/collectes/{id}/statut/     → mettre à jour le statut (collecteur/admin)
    - DELETE /api/collectes/{id}/            → supprimer (admin)
    """

    def get_queryset(self):
        """
        - Un admin voit toutes les collectes.
        - Un collecteur connecté voit uniquement ses propres collectes.
        - Tout autre utilisateur reçoit un queryset vide.
        """
        utilisateur = self.request.user

        # Précharge les relations pour éviter les requêtes N+1.
        base_queryset = Collecte.objects.select_related(
            'idCollecteur',
            'idPoint',
            'idDemande__idUtilisateur',
            'idDemande__idTypeDechet',
        ).order_by('-datePlanifiee')

        # L'admin voit toutes les collectes.
        if utilisateur.is_authenticated and utilisateur.role == 'admin':
            return base_queryset

        # Le collecteur ne voit que ses propres collectes.
        # On vérifie d'abord qu'il a bien un profil collecteur validé.
        try:
            collecteur = Collecteur.objects.get(idUtilisateur=utilisateur)
            return base_queryset.filter(idCollecteur=collecteur)
        except Collecteur.DoesNotExist:
            # L'utilisateur n'est pas un collecteur → liste vide.
            return Collecte.objects.none()

    def get_serializer_class(self):
        # Création : serializer d'écriture simplifié.
        if self.action == 'create':
            return CollecteCreationSerializer

        # Mise à jour du statut : serializer dédié.
        if self.action == 'changer_statut':
            return CollecteStatutSerializer

        # Lecture : serializer complet.
        return CollecteSerializer

    def get_permissions(self):
        # Création et consultation accessibles aux utilisateurs connectés.
        if self.action in ['create', 'list', 'retrieve']:
            return [IsAuthenticated()]

        # Modification et suppression réservées aux admins.
        return [IsAdmin()]

    def perform_create(self, serializer):
        """
        Associe automatiquement le profil collecteur
        de l'utilisateur connecté à la collecte créée.
        Retourne une erreur 400 claire si l'utilisateur
        n'a pas de profil Collecteur en base.
        """
        from rest_framework.exceptions import ValidationError

        try:
            collecteur = Collecteur.objects.get(idUtilisateur=self.request.user)
        except Collecteur.DoesNotExist:
            raise ValidationError(
                {'detail': (
                    'Vous devez créer un profil collecteur avant de planifier '
                    'une collecte. Rendez-vous sur POST /api/collecteurs/.'
                )}
            )

        serializer.save(idCollecteur=collecteur)

    @action(detail=True, methods=['patch'], url_path='statut', permission_classes=[IsAuthenticated])
    def changer_statut(self, request, pk=None):
        """
        Action personnalisée pour mettre à jour le statut d'une collecte.
        URL : PATCH /api/collectes/{id}/statut/
        Corps attendu : { "statut": "terminee", "dateRealisation": "...", "quantiteRecuperee": 12.5 }
        Valeurs possibles : planifiee, en_cours, terminee, annulee
        """
        collecte = self.get_object()

        # Valide et applique le nouveau statut.
        serializer = CollecteStatutSerializer(
            collecte,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            # Retourne la collecte complète après mise à jour.
            return Response(
                CollecteSerializer(collecte).data,
                status=status.HTTP_200_OK
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )