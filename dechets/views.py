from django.db import transaction
from django.db.models import F
from rest_framework import status, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import PanierDechet, TypeDechet, ConseilTri, PrixDechet
from .serializers import (
    PanierDechetSerializer,
    TypeDechetSerializer,
    ConseilTriSerializer,
    PrixDechetSerializer,
)
from users.permissions import IsAdmin
from collecteurs.models import Collecteur
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
    Expose les tarifs généraux historiques et les tarifs propres à chaque collecteur.
    """

    queryset = PrixDechet.objects.select_related('idTypeDechet').all()
    serializer_class = PrixDechetSerializer

    class IsCollecteurValide(BasePermission):
        """Autorise la gestion des tarifs aux collecteurs validés."""

        def has_permission(self, request, view):
            return request.user.is_authenticated and Collecteur.objects.filter(
                idUtilisateur=request.user,
                statutValidation='valide',
            ).exists()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticatedOrReadOnly()]

        if self.request.user.is_authenticated and self.request.user.role == 'admin':
            return [IsAdmin()]
        return [self.IsCollecteurValide()]

    def get_queryset(self):
        tarifs = self.queryset
        utilisateur = self.request.user

        if utilisateur.is_authenticated and utilisateur.role == 'admin':
            collecteur_id = self.request.query_params.get('idCollecteur')
            return self.filtrer_par_collecteur(tarifs, collecteur_id)

        if utilisateur.is_authenticated:
            collecteur = Collecteur.objects.filter(idUtilisateur=utilisateur).first()
            if collecteur:
                return tarifs.filter(idCollecteur=collecteur)

        collecteur_id = self.request.query_params.get('idCollecteur')
        if collecteur_id:
            return self.filtrer_par_collecteur(tarifs, collecteur_id)

        return tarifs.filter(idCollecteur__isnull=True)

    @staticmethod
    def filtrer_par_collecteur(tarifs, collecteur_id):
        if not collecteur_id:
            return tarifs
        try:
            collecteur_id = int(collecteur_id)
        except (TypeError, ValueError) as erreur:
            raise ValidationError({
                'idCollecteur': 'Fournissez un identifiant de collecteur valide.'
            }) from erreur
        return tarifs.filter(idCollecteur_id=collecteur_id)

    def perform_create(self, serializer):
        utilisateur = self.request.user
        if utilisateur.role == 'admin':
            serializer.save()
            return

        collecteur = Collecteur.objects.get(
            idUtilisateur=utilisateur,
            statutValidation='valide',
        )
        serializer.save(idCollecteur=collecteur)


class PanierDechetViewSet(viewsets.ModelViewSet):
    """Expose uniquement les paniers du citoyen authentifié."""

    serializer_class = PanierDechetSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        return PanierDechet.objects.filter(
            idUtilisateur=self.request.user
        ).select_related('idTypeDechet').order_by('idTypeDechet__nom')

    def create(self, request, *args, **kwargs):
        """Ajoute une quantité au panier existant au lieu de créer un doublon."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        type_dechet = serializer.validated_data.get('idTypeDechet')
        nombre_objets = serializer.validated_data.get('nombreDisponible')
        if type_dechet is None or nombre_objets is None:
            raise ValidationError({
                'detail': 'idTypeDechet et nombreDisponible sont obligatoires.'
            })
        if nombre_objets <= 0:
            raise ValidationError({
                'nombreDisponible': 'Le nombre d’objets à ajouter doit être supérieur à zéro.'
            })

        with transaction.atomic():
            # La contrainte unique protège aussi contre deux ajouts concurrents.
            panier, _ = PanierDechet.objects.get_or_create(
                idUtilisateur=request.user,
                idTypeDechet=type_dechet,
                defaults={'nombreDisponible': 0, 'unite': 'objet'},
            )
            panier = PanierDechet.objects.select_for_update().get(pk=panier.pk)
            PanierDechet.objects.filter(pk=panier.pk).update(
                nombreDisponible=F('nombreDisponible') + nombre_objets,
            )
            panier.refresh_from_db()

        return Response(
            self.get_serializer(panier).data,
            status=status.HTTP_201_CREATED,
        )