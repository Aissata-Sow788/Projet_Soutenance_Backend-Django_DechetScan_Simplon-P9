import json
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Sum

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdmin
from collecteurs.models import Collecteur

# Réutilise les utilitaires PayDunya définis dans collecteurs/views.py.
from collecteurs.views import (
    appeler_paydunya,
    obtenir_url_callback_paydunya,
    PayDunyaError,
)

from .models import VenteDechet
from .serializers import (
    VenteDechetSerializer,
    VenteDechetCreationSerializer,
    VenteDechetStatutSerializer,
)


class VenteDechetViewSet(viewsets.ModelViewSet):
    """
    Endpoints CRUD pour la gestion des ventes de déchets.

    GET    /api/ventes/              : liste des ventes selon le rôle
    GET    /api/ventes/{id}/         : détail d'une vente
    POST   /api/ventes/              : création d'une vente
    PATCH  /api/ventes/{id}/statut/  : modification du statut
    DELETE /api/ventes/{id}/         : suppression d'une vente
    """

    def get_queryset(self):
        utilisateur = self.request.user

        base_queryset = VenteDechet.objects.select_related(
            'idUtilisateur',
            'idCollecteur__idUtilisateur',
        ).prefetch_related(
            'details__idPanier__idTypeDechet',
        ).order_by('-dateVente')

        # L'admin voit toutes les ventes.
        if utilisateur.is_authenticated and utilisateur.role == 'admin':
            return base_queryset

        # Le collecteur voit les ventes qui lui sont associées.
        collecteur = Collecteur.objects.filter(
            idUtilisateur=utilisateur,
        ).first()

        if collecteur:
            return base_queryset.filter(idCollecteur=collecteur)

        # Le citoyen voit ses propres ventes.
        return base_queryset.filter(idUtilisateur=utilisateur)

    def get_serializer_class(self):
        if self.action == 'create':
            return VenteDechetCreationSerializer

        if self.action == 'changer_statut':
            return VenteDechetStatutSerializer

        return VenteDechetSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        vente = serializer.instance

        serializer_reponse = VenteDechetSerializer(
            vente,
            context=self.get_serializer_context(),
        )

        return Response(
            serializer_reponse.data,
            status=status.HTTP_201_CREATED,
        )

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve']:
            return [IsAuthenticated()]

        return [IsAdmin()]

    def perform_create(self, serializer):
        serializer.save(idUtilisateur=self.request.user)

    @action(
        detail=True,
        methods=['patch'],
        url_path='statut',
        permission_classes=[IsAdmin],
    )
    def changer_statut(self, request, pk=None):
        """
        Met à jour le statut de paiement d'une vente.
        Valeurs : en_attente, paye, echoue, rembourse.
        """
        vente = self.get_object()

        serializer = VenteDechetStatutSerializer(
            vente,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                VenteDechetSerializer(vente).data,
                status=status.HTTP_200_OK,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


# ============================================================
# PAIEMENT CITOYEN VIA PAYDUNYA
# ============================================================

class VentePaiementInitierView(APIView):
    """
    Initie le paiement d'une vente via PayDunya.

    POST /api/ventes/paiement/initier/

    Corps :
    {
        "idVente": 5,
        "operateur": "wave"
    }
    """

    permission_classes = [IsAuthenticated]

    OPERATEURS = {
        'wave': 'wave-senegal',
        'orange_money': 'orange-money-senegal',
    }

    def post(self, request):
        # Récupère le profil collecteur validé.
        collecteur = Collecteur.objects.filter(
            idUtilisateur=request.user,
            statutValidation='valide',
        ).first()

        if not collecteur:
            return Response(
                {
                    'detail': (
                        'Vous devez avoir un profil collecteur validé '
                        'pour initier un paiement.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Vérifie les paramètres de la requête.
        id_vente = request.data.get('idVente')
        operateur = request.data.get('operateur', '')

        if not id_vente:
            return Response(
                {'detail': 'Le champ idVente est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(operateur, str):
            return Response(
                {'detail': 'L’opérateur de paiement est invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        operateur = operateur.strip()

        if operateur not in self.OPERATEURS:
            return Response(
                {
                    'detail': (
                        'Opérateur invalide. Valeurs acceptées : '
                        f'{list(self.OPERATEURS.keys())}'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Récupère la vente et ses détails.
        try:
            vente = VenteDechet.objects.select_related(
                'idUtilisateur',
                'idCollecteur',
            ).prefetch_related(
                'details__idPanier__idTypeDechet',
            ).get(
                idVente=id_vente,
                idCollecteur=collecteur,
            )
        except (VenteDechet.DoesNotExist, ValueError, TypeError):
            return Response(
                {
                    'detail': (
                        'Vente introuvable ou vous n’êtes pas '
                        'le collecteur associé à cette vente.'
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Vérifie le statut de paiement.
        if vente.statutPaiement != 'en_attente':
            return Response(
                {
                    'detail': (
                        'Cette vente ne peut pas être payée '
                        f'(statut actuel : {vente.statutPaiement}).'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Vérifie le montant minimum PayDunya.
        if vente.prixPaye < 200:
            return Response(
                {
                    'detail': (
                        'Le montant de la vente est inférieur au '
                        'minimum PayDunya (200 FCFA).'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Vérifie la configuration PayDunya.
        configuration_manquante = [
            nom
            for nom, valeur in (
                ('PAYDUNYA_MASTER_KEY', settings.PAYDUNYA_MASTER_KEY),
                ('PAYDUNYA_PRIVATE_KEY', settings.PAYDUNYA_PRIVATE_KEY),
                ('PAYDUNYA_TOKEN', settings.PAYDUNYA_TOKEN),
            )
            if not valeur
        ]

        callback_url = obtenir_url_callback_paydunya()

        if configuration_manquante or not callback_url:
            details = []

            if configuration_manquante:
                details.append(
                    'Les clés PayDunya sont absentes de la configuration '
                    'backend.'
                )

            if not callback_url:
                details.append(
                    'Aucun callback public configuré. Vérifiez la '
                    'configuration de votre URL de callback.'
                )

            return Response(
                {
                    'detail': ' '.join(details),
                    'configurationManquante': configuration_manquante,
                    'callbackPublicDisponible': callback_url is not None,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Génère une référence unique pour la transaction.
        reference = f'VP-{uuid.uuid4().hex}'

        # Informations du collecteur qui paie.
        compte_collecteur = collecteur.idUtilisateur

        client = {
            'name': (
                f'{compte_collecteur.first_name} '
                f'{compte_collecteur.last_name}'
            ).strip() or 'Collecteur',
            'email': compte_collecteur.email,
            'phone': compte_collecteur.telephone or '',
        }

        # URLs de retour vers Angular.
        base_frontend = settings.PAYDUNYA_FRONTEND_URL.rstrip('/')

        retour = (
            f'{base_frontend}/collecteur/paiements'
            f'?reference={reference}'
        )
        annulation = (
            f'{base_frontend}/collecteur/paiements?paiement=annule'
        )

        # Récupère les types de déchets présents dans les détails.
        types_dechets = list(
            vente.details.values_list(
                'idPanier__idTypeDechet__nom',
                flat=True,
            ).distinct()
        )

        type_dechet = ', '.join(
            nom for nom in types_dechets if nom
        ) or 'Déchet'

        # CORRECTION : le modèle VenteDechet ne possède pas
        # d'attribut direct "quantite". Le poids total est calculé
        # à partir des détails de vente.
        poids_total = vente.details.aggregate(
            total=Sum('poidsKg')
        )['total'] or 0

        citoyen_nom = ''

        if vente.idUtilisateur:
            citoyen_nom = (
                f'{vente.idUtilisateur.first_name} '
                f'{vente.idUtilisateur.last_name}'
            ).strip()

        # Construit la facture PayDunya.
        facture = {
            'invoice': {
                'items': {
                    'vente_dechet': {
                        'name': (
                            f'Achat {type_dechet} — '
                            f'{poids_total} kg'
                        ),
                        'quantity': 1,
                        'unit_price': int(vente.prixPaye),
                        'total_price': int(vente.prixPaye),
                        'description': (
                            f'Paiement citoyen {citoyen_nom} '
                            f'pour vente #{vente.idVente}'
                        ),
                    },
                },
                'total_amount': int(vente.prixPaye),
                'description': (
                    f'Paiement vente déchets {type_dechet} — '
                    f'{reference}'
                ),
                'customer': client,
                'channels': self.OPERATEURS[operateur],
            },
            'store': {
                'name': 'DechetScan',
                'tagline': 'La collecte intelligente des déchets',
                'phone': settings.PAYDUNYA_STORE_PHONE,
                'postal_address': settings.PAYDUNYA_STORE_ADDRESS,
                'website_url': settings.PAYDUNYA_STORE_WEBSITE,
            },
            'actions': {
                'cancel_url': annulation,
                'return_url': retour,
                'callback_url': callback_url,
            },
            'custom_data': {
                'reference': reference,
                'vente_id': vente.idVente,
            },
        }

        # Crée la facture PayDunya.
        try:
            resultat = appeler_paydunya(
                'checkout-invoice/create',
                method='POST',
                body=facture,
            )
        except PayDunyaError as error:
            return Response(
                {'detail': str(error)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Vérifie la réponse PayDunya.
        token = resultat.get('token')
        url_paiement = resultat.get('response_text')

        parsed_url = (
            urlparse(url_paiement)
            if isinstance(url_paiement, str)
            else None
        )

        if (
            resultat.get('response_code') != '00'
            or not token
            or not parsed_url
            or parsed_url.scheme != 'https'
            or parsed_url.netloc not in {
                'app.paydunya.com',
                'paydunya.com',
            }
        ):
            return Response(
                {
                    'detail': resultat.get(
                        'response_text',
                        'PayDunya n’a pas créé la facture.',
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Enregistre les informations de paiement sur la vente.
        vente.referencePaiement = reference
        vente.tokenPayDunya = token
        vente.methodePaiement = operateur.replace('_', ' ').title()

        vente.save(
            update_fields=[
                'referencePaiement',
                'tokenPayDunya',
                'methodePaiement',
            ]
        )

        return Response(
            {
                'reference': reference,
                'urlPaiement': url_paiement,
            },
            status=status.HTTP_201_CREATED,
        )


class VentePaiementVerifierView(APIView):
    """
    Vérifie le statut d'un paiement auprès de PayDunya.

    GET /api/ventes/paiement/verifier/?reference=VP-xxx
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        reference = request.query_params.get('reference', '').strip()

        if not reference:
            return Response(
                {'detail': 'Le paramètre reference est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        collecteur = Collecteur.objects.filter(
            idUtilisateur=request.user,
        ).first()

        if not collecteur:
            return Response(
                {'detail': 'Profil collecteur introuvable.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        vente = VenteDechet.objects.filter(
            referencePaiement=reference,
            idCollecteur=collecteur,
        ).first()

        if not vente:
            return Response(
                {'detail': 'Référence de paiement introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if vente.statutPaiement == 'paye':
            return Response({
                'statutPaiement': 'paye',
                'estPaye': True,
            })

        if not vente.tokenPayDunya:
            return Response(
                {'detail': 'Aucune facture PayDunya associée à cette vente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resultat = appeler_paydunya(
                f'checkout-invoice/confirm/{vente.tokenPayDunya}'
            )
        except PayDunyaError as error:
            return Response(
                {'detail': str(error)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        facture = resultat.get('data', resultat)

        est_paye = (
            facture.get('response_code') == '00'
            and str(facture.get('status', '')).lower() == 'completed'
        )

        if est_paye and vente.statutPaiement != 'paye':
            vente.statutPaiement = 'paye'
            vente.save(update_fields=['statutPaiement'])

        return Response({
            'statutPaiement': 'paye' if est_paye else vente.statutPaiement,
            'estPaye': est_paye,
        })


class VentePaiementCallbackView(APIView):
    """
    Endpoint IPN appelé par PayDunya après le paiement.

    POST /api/ventes/paiement/ipn/
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data.get('data', request.data)

        if not isinstance(data, dict):
            return Response(
                {'detail': 'Notification PayDunya invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice = data.get('invoice', {})
        token = (
            invoice.get('token')
            if isinstance(invoice, dict)
            else None
        ) or data.get('token')

        if not token:
            return Response(
                {
                    'detail': (
                        'Notification PayDunya invalide : '
                        'token manquant.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        vente = VenteDechet.objects.filter(
            tokenPayDunya=token,
        ).first()

        if not vente:
            return Response(
                {'received': True},
                status=status.HTTP_200_OK,
            )

        # Vérifie le statut réel auprès de PayDunya.
        try:
            resultat = appeler_paydunya(
                f'checkout-invoice/confirm/{vente.tokenPayDunya}'
            )
        except PayDunyaError:
            return Response(
                {'received': True},
                status=status.HTTP_200_OK,
            )

        facture = resultat.get('data', resultat)

        est_paye = (
            facture.get('response_code') == '00'
            and str(facture.get('status', '')).lower() == 'completed'
        )

        if est_paye and vente.statutPaiement != 'paye':
            vente.statutPaiement = 'paye'
            vente.save(update_fields=['statutPaiement'])

        return Response(
            {'received': True},
            status=status.HTTP_200_OK,
        )
