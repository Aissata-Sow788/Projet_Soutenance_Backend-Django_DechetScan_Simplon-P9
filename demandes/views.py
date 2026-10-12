from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers as drf_serializers
from django.db import transaction
from django.db.models import Q
from dechets.services import restituer_quantites_paniers
from drf_spectacular.utils import extend_schema
from notifications.services import (
    notifier_collecteur_nouvelle_demande,
    notifier_citoyen_statut_demande,
)

from users.permissions import IsAdmin
from collecteurs.models import Collecteur
from .models import DemandeCollecte
from .serializers import (
    DemandeCollecteSerializer,
    DemandeCollecteCreationSerializer,
    DemandeCollecteStatutSerializer,
)


class DemandeCollecteAccepterSerializer(drf_serializers.Serializer):
    """
    Serializer vide pour l'action accepter.
    L'endpoint ne requiert aucun corps — seul l'id dans l'URL est nécessaire.
    Ce serializer existe uniquement pour que Swagger affiche
    un body vide au lieu du serializer de création.
    """
    pass


class DemandeCollecteViewSet(viewsets.ModelViewSet):
    """
    Endpoints pour la gestion des demandes de collecte.

    - GET    /api/demandes/              → liste toutes les demandes (admin/collecteur)
                                           ou seulement les siennes (citoyen)
    - GET    /api/demandes/{id}/         → détail d'une demande
    - POST   /api/demandes/              → créer une demande (citoyen connecté)
    - PATCH  /api/demandes/{id}/accepter/→ collecteur accepte la demande (atomique)
    - PATCH  /api/demandes/{id}/statut/  → transition du statut (admin/collecteur attribué)
    - POST   /api/demandes/{id}/refuser/ → refus individuel d'un collecteur
    - DELETE /api/demandes/{id}/         → supprimer une demande (admin)
    """

    def get_queryset(self):
        """
        - Un admin voit toutes les demandes.
        - Un collecteur validé voit toutes les demandes en attente ou acceptées.
        - Un citoyen voit uniquement ses propres demandes.
        """
        utilisateur = self.request.user

        # L'admin peut voir toutes les demandes.
        if utilisateur.is_authenticated and utilisateur.role == 'admin':
            return DemandeCollecte.objects.select_related(
                'idUtilisateur', 'collecteurAttribue__idUtilisateur'
            ).prefetch_related(
                'details__idPanier__idTypeDechet'
            ).order_by('-dateDemande')

        # Un collecteur validé voit toutes les demandes disponibles.
        try:
            collecteur = Collecteur.objects.get(idUtilisateur=utilisateur)
            if collecteur.statutValidation == 'valide':
                return DemandeCollecte.objects.select_related(
                    'idUtilisateur', 'collecteurAttribue__idUtilisateur'
                ).prefetch_related(
                    'details__idPanier__idTypeDechet'
                ).filter(
                    Q(collecteurAttribue=collecteur) |
                    (Q(statut='en_attente') & ~Q(refuseurs=collecteur))
                ).distinct().order_by('-dateDemande')
        except Collecteur.DoesNotExist:
            pass

        # Le citoyen ne voit que ses propres demandes.
        return DemandeCollecte.objects.filter(
            idUtilisateur=utilisateur
        ).select_related(
            'idUtilisateur', 'collecteurAttribue__idUtilisateur'
        ).prefetch_related(
            'details__idPanier__idTypeDechet'
        ).order_by('-dateDemande')

    def get_serializer_class(self):
        if self.action == 'create':
            return DemandeCollecteCreationSerializer
        if self.action == 'changer_statut':
            return DemandeCollecteStatutSerializer
        # L'action accepter n'a pas de body : serializer vide.
        if self.action == 'accepter':
            return DemandeCollecteAccepterSerializer
        return DemandeCollecteSerializer

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve', 'accepter', 'refuser']:
            return [IsAuthenticated()]
        if self.action == 'changer_statut':
            return [IsAuthenticated()]
        return [IsAdmin()]

    def perform_create(self, serializer):
        """Associe automatiquement l'utilisateur connecté à la demande."""
        demande = serializer.save(idUtilisateur=self.request.user)
        notifier_collecteur_nouvelle_demande(demande)

    def create(self, request, *args, **kwargs):
        """Retourne la demande complète créée, dont son identifiant de suivi."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        demande = DemandeCollecteSerializer(
            serializer.instance,
            context=self.get_serializer_context()
        )
        return Response(
            demande.data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=None,
        responses=DemandeCollecteSerializer,
        summary="Accepter une demande de collecte",
        description=(
            "Le collecteur connecté accepte une demande en attente. "
            "Aucun corps n'est requis — seul l'id dans l'URL suffit. "
            "Retourne 409 si la demande est déjà acceptée par un autre collecteur."
        )
    )
    @action(detail=True, methods=['patch'], url_path='accepter')
    def accepter(self, request, pk=None):
        """
        Action dédiée à l'acceptation d'une demande par un collecteur.
        URL : PATCH /api/demandes/{id}/accepter/

        Règles métier appliquées atomiquement :
        1. Le demandeur doit avoir un profil Collecteur validé.
        2. La demande doit être en statut 'en_attente'.
           Si elle est déjà 'acceptee', retourne 409 CONFLICT
           (protection contre la double acceptation).
        3. La demande passe à 'acceptee' et collecteurAttribue = ce collecteur.
        4. Les autres collecteurs ne peuvent plus l'accepter.

        Le bloc select_for_update() verrouille la ligne en base
        pendant la transaction pour éviter les conditions de course
        (race condition) si deux collecteurs acceptent en même temps.
        """

        # Vérifie que le demandeur est un collecteur validé.
        try:
            collecteur = Collecteur.objects.get(
                idUtilisateur=request.user,
                statutValidation='valide'
            )
        except Collecteur.DoesNotExist:
            return Response(
                {
                    'detail': (
                        'Vous devez avoir un profil collecteur validé '
                        'pour accepter une demande.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Transaction atomique + verrou de ligne pour éviter la double acceptation.
        with transaction.atomic():

            # select_for_update() pose un verrou exclusif sur cette ligne
            # jusqu'à la fin de la transaction.
            # Si un autre collecteur est en train d'accepter la même demande
            # au même moment, il attendra la fin de cette transaction.
            try:
                demande = DemandeCollecte.objects.select_for_update().get(
                    pk=pk
                )
            except DemandeCollecte.DoesNotExist:
                return Response(
                    {'detail': 'Demande introuvable.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Vérifie que la demande est encore en attente.
            # Si un autre collecteur vient d'accepter pendant l'attente
            # du verrou, on retourne 409 Conflict.
            if demande.statut != 'en_attente':
                return Response(
                    {
                        'detail': (
                            'Cette demande a déjà été acceptée par un autre '
                            'collecteur ou n\'est plus disponible.'
                        )
                    },
                    status=status.HTTP_409_CONFLICT
                )

            if demande.refuseurs.filter(pk=collecteur.pk).exists():
                return Response(
                    {'detail': 'Vous avez déjà refusé cette demande.'},
                    status=status.HTTP_409_CONFLICT
                )

            # Attribue le collecteur et change le statut.
            demande.collecteurAttribue = collecteur
            demande.statut = 'acceptee'
            demande.save(update_fields=['collecteurAttribue', 'statut'])

        # Recharge la demande avec ses relations pour la sérialisation.
        demande.refresh_from_db()
        notifier_citoyen_statut_demande(demande, 'acceptee')
        return Response(
            DemandeCollecteSerializer(demande).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='refuser')
    def refuser(self, request, pk=None):
        """Masque une demande en attente uniquement pour le collecteur courant."""
        try:
            collecteur = Collecteur.objects.get(
                idUtilisateur=request.user,
                statutValidation='valide'
            )
        except Collecteur.DoesNotExist:
            return Response(
                {'detail': 'Votre profil collecteur doit être validé pour refuser une demande.'},
                status=status.HTTP_403_FORBIDDEN
            )

        with transaction.atomic():
            try:
                demande = DemandeCollecte.objects.select_for_update().get(pk=pk)
            except DemandeCollecte.DoesNotExist:
                return Response(
                    {'detail': 'Demande introuvable.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if demande.statut != 'en_attente' or demande.collecteurAttribue_id:
                return Response(
                    {'detail': 'Cette demande n’est plus disponible.'},
                    status=status.HTTP_409_CONFLICT
                )

            demande.refuseurs.add(collecteur)

        notifier_citoyen_statut_demande(demande, 'refus_individuel')
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['patch'], url_path='statut')
    def changer_statut(self, request, pk=None):
        """
        Action pour changer le statut d'une demande (admin ou collecteur assigné).
        URL : PATCH /api/demandes/{id}/statut/
        Corps : { "statut": "en_cours" }
        Le collecteur assigné peut uniquement passer de acceptee à en_cours,
        puis de en_cours à terminee. L'admin garde la gestion complète.

        Note : pour accepter une demande, utiliser /accepter/ à la place.
        """
        demande = self.get_object()
        collecteur = None
        if request.user.role != 'admin':
            try:
                collecteur = Collecteur.objects.get(
                    idUtilisateur=request.user,
                    statutValidation='valide'
                )
            except Collecteur.DoesNotExist:
                return Response(
                    {'detail': 'Seul le collecteur affecté ou un administrateur peut modifier cette demande.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            if demande.collecteurAttribue_id != collecteur.pk:
                return Response(
                    {'detail': 'Cette demande ne vous est pas attribuée.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        with transaction.atomic():
            demande = DemandeCollecte.objects.select_for_update().get(
                pk=demande.pk
            )
            ancien_statut = demande.statut
            nouveau_statut = request.data.get('statut')

            # Une demande annulée est terminale : son stock a déjà été rendu.
            if demande.stockRestitue and nouveau_statut != 'annulee':
                return Response(
                    {'detail': 'Une demande annulée ne peut pas être réactivée.'},
                    status=status.HTTP_409_CONFLICT
                )
            if demande.statut == 'terminee' and nouveau_statut != 'terminee':
                return Response(
                    {'detail': 'Une demande terminée ne peut pas être réouverte ou annulée.'},
                    status=status.HTTP_409_CONFLICT
                )

            if collecteur:
                transitions = {
                    'acceptee': {'planifiee', 'en_cours'},
                    'planifiee': 'en_cours',
                    'en_cours': 'terminee',
                }
                transition_autorisee = transitions.get(demande.statut)
                if isinstance(transition_autorisee, set):
                    transition_permise = nouveau_statut in transition_autorisee
                else:
                    transition_permise = transition_autorisee == nouveau_statut
                if not transition_permise:
                    return Response(
                        {'detail': 'Transition non autorisée. Une demande acceptée peut être planifiée ou passer en cours, puis une demande planifiée passe en cours avant d’être terminée.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if demande.collecteurAttribue_id != collecteur.pk:
                    return Response(
                        {'detail': 'Cette demande ne vous est pas attribuée.'},
                        status=status.HTTP_403_FORBIDDEN
                    )

            serializer = DemandeCollecteStatutSerializer(
                demande,
                data=request.data,
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            if nouveau_statut == 'annulee' and not demande.stockRestitue:
                # Le verrou et le marqueur garantissent une restitution unique.
                restituer_quantites_paniers(demande.details.all())
                demande.stockRestitue = True
                demande.save(update_fields=['stockRestitue'])

        if demande.statut != ancien_statut:
            notifier_citoyen_statut_demande(demande, demande.statut)

        return Response(
            DemandeCollecteSerializer(
                demande,
                context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        demande = self.get_object()
        with transaction.atomic():
            demande = DemandeCollecte.objects.select_for_update().get(
                pk=demande.pk
            )
            # Les demandes terminées ou déjà annulées ne rendent pas le stock.
            if (
                not demande.stockRestitue
                and demande.statut in {'en_attente', 'acceptee'}
            ):
                restituer_quantites_paniers(demande.details.all())
            demande.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
