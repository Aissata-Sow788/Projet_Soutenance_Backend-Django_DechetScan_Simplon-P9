import json
import uuid
from urllib.parse import urlparse

from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdmin
from collecteurs.models import Collecteur

# Réutilise les utilitaires PayDunya définis dans collecteurs/views.py
# pour éviter toute duplication de code.
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

    - GET    /api/ventes/              → admin: toutes | collecteur: ses achats | citoyen: ses ventes
    - GET    /api/ventes/{id}/         → détail d'une vente
    - POST   /api/ventes/              → créer une vente (citoyen connecté)
    - PATCH  /api/ventes/{id}/statut/  → mettre à jour le statut (collecteur)
    - DELETE /api/ventes/{id}/         → supprimer une vente (collecteur)
    """

    def get_queryset(self):
        """
        Filtre les ventes selon le rôle de l'utilisateur connecté :
        - Admin       → toutes les ventes
        - Collecteur  → les ventes où il est l'acheteur (idCollecteur)
        - Citoyen     → les ventes qu'il a soumises (idUtilisateur)
        """
        utilisateur = self.request.user

        # Précharge les relations pour éviter les requêtes N+1.
        base_queryset = VenteDechet.objects.select_related(
            'idUtilisateur',
            'idCollecteur__idUtilisateur',
            'idTypeDechet'
        ).order_by('-dateVente')

        # L'admin voit tout.
        if utilisateur.is_authenticated and utilisateur.role == 'admin':
            return base_queryset

        # Le collecteur voit les ventes qu'il a achetées.
        collecteur = Collecteur.objects.filter(idUtilisateur=utilisateur).first()
        if collecteur:
            return base_queryset.filter(idCollecteur=collecteur)

        # Le citoyen voit ses propres ventes.
        return base_queryset.filter(idUtilisateur=utilisateur)

    def get_serializer_class(self):
        # Création : serializer simplifié sans idUtilisateur.
        if self.action == 'create':
            return VenteDechetCreationSerializer

        # Changement de statut : serializer dédié.
        if self.action == 'changer_statut':
            return VenteDechetStatutSerializer

        # Lecture : serializer complet.
        return VenteDechetSerializer

    def get_permissions(self):
        # Création et consultation accessibles aux utilisateurs connectés.
        if self.action in ['create', 'list', 'retrieve']:
            return [IsAuthenticated()]

        # Modification et suppression réservées aux admins.
        return [IsAdmin()]

    def perform_create(self, serializer):
        """
        Associe automatiquement l'utilisateur connecté à la vente
        (il est le citoyen vendeur).
        """
        serializer.save(idUtilisateur=self.request.user)

    @action(
        detail=True,
        methods=['patch'],
        url_path='statut',
        permission_classes=[IsAdmin]
    )
    def changer_statut(self, request, pk=None):
        """
        Met à jour le statut de paiement d'une vente (admin uniquement).
        URL  : PATCH /api/ventes/{id}/statut/
        Corps: { "statutPaiement": "paye" }
        Valeurs: en_attente | paye | echoue | rembourse
        """
        vente = self.get_object()

        serializer = VenteDechetStatutSerializer(
            vente, data=request.data, partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                VenteDechetSerializer(vente).data,
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# PAIEMENT CITOYEN VIA PAYDUNYA
# ============================================================
# Flux :
#   1. Collecteur → POST /api/ventes/paiement/initier/
#      → Django crée une facture PayDunya et retourne urlPaiement
#   2. Collecteur est redirigé vers la page PayDunya pour payer
#   3. PayDunya redirige le collecteur vers /collecteur/paiements?reference=...
#   4. Angular → GET /api/ventes/paiement/verifier/?reference=...
#      → Django interroge PayDunya pour confirmer le paiement
#   5. PayDunya notifie Django via IPN → POST /api/ventes/paiement/ipn/
# ============================================================

class VentePaiementInitierView(APIView):
    """
    Initie un paiement PayDunya pour régler une vente de déchets.
    Le collecteur connecté paie le citoyen vendeur.

    URL  : POST /api/ventes/paiement/initier/
    Corps: { "idVente": 5, "operateur": "wave" }
    Retour: { "reference": "VP-xxx", "urlPaiement": "https://..." }

    Pré-conditions vérifiées :
    - L'utilisateur connecté doit avoir un profil Collecteur validé.
    - La vente doit lui appartenir (idCollecteur).
    - La vente doit être en statut 'en_attente'.
    - Le montant PayDunya minimum est 200 FCFA.
    """

    permission_classes = [IsAuthenticated]

    # Opérateurs de paiement acceptés (canaux PayDunya).
    OPERATEURS = {
        'wave':         'wave-senegal',
        'orange_money': 'orange-money-senegal',
    }

    def post(self, request):

        # ── Récupère le profil collecteur de l'utilisateur connecté ──
        collecteur = Collecteur.objects.filter(
            idUtilisateur=request.user,
            statutValidation='valide'
        ).first()

        if not collecteur:
            return Response(
                {
                    'detail': (
                        'Vous devez avoir un profil collecteur validé '
                        'pour initier un paiement.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # ── Valide les paramètres du corps de la requête ──
        id_vente  = request.data.get('idVente')
        operateur = request.data.get('operateur', '').strip()

        if not id_vente:
            return Response(
                {'detail': 'Le champ idVente est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if operateur not in self.OPERATEURS:
            return Response(
                {
                    'detail': (
                        f"Opérateur invalide. Valeurs acceptées : "
                        f"{list(self.OPERATEURS.keys())}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Récupère la vente et vérifie qu'elle appartient au collecteur ──
        try:
            vente = VenteDechet.objects.select_related(
                'idUtilisateur', 'idTypeDechet'
            ).get(
                idVente=id_vente,
                idCollecteur=collecteur
            )
        except VenteDechet.DoesNotExist:
            return Response(
                {
                    'detail': (
                        'Vente introuvable ou vous n\'êtes pas '
                        'le collecteur associé à cette vente.'
                    )
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # ── Vérifie que la vente est encore en attente de paiement ──
        if vente.statutPaiement != 'en_attente':
            return Response(
                {
                    'detail': (
                        f"Cette vente ne peut pas être payée "
                        f"(statut actuel : {vente.statutPaiement})."
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        # ── Vérifie le montant minimum PayDunya (200 FCFA) ──
        if vente.prixPaye < 200:
            return Response(
                {
                    'detail': (
                        'Le montant de la vente est inférieur au minimum '
                        'PayDunya (200 FCFA).'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Vérifie la configuration PayDunya et le callback public ──
        configuration_manquante = [
            nom for nom, valeur in (
                ('PAYDUNYA_MASTER_KEY', settings.PAYDUNYA_MASTER_KEY),
                ('PAYDUNYA_PRIVATE_KEY', settings.PAYDUNYA_PRIVATE_KEY),
                ('PAYDUNYA_TOKEN', settings.PAYDUNYA_TOKEN),
            ) if not valeur
        ]
        callback_url = obtenir_url_callback_paydunya()

        if configuration_manquante or not callback_url:
            details = []
            if configuration_manquante:
                details.append(
                    'Les clés PayDunya sont absentes de la configuration backend.'
                )
            if not callback_url:
                details.append(
                    'Aucun callback public configuré. Démarrez ngrok '
                    'avec « ngrok http 8000 ».'
                )
            return Response(
                {
                    'detail': ' '.join(details),
                    'configurationManquante': configuration_manquante,
                    'callbackPublicDisponible': callback_url is not None,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # ── Génère une référence unique pour cette transaction ──
        # Préfixe VP (Vente Paiement) pour distinguer des abonnements (DS-).
        reference = f'VP-{uuid.uuid4().hex}'

        # ── Prépare les informations du client (collecteur payeur) ──
        compte_collecteur = collecteur.idUtilisateur
        client = {
            'name': (
                f'{compte_collecteur.first_name} '
                f'{compte_collecteur.last_name}'
            ).strip() or 'Collecteur',
            'email': compte_collecteur.email,
            'phone': compte_collecteur.telephone or '',
        }

        # ── Construit les URLs de retour vers Angular ──
        base_frontend = settings.PAYDUNYA_FRONTEND_URL.rstrip('/')
        # URL de retour après paiement réussi.
        retour    = f'{base_frontend}/collecteur/paiements?reference={reference}'
        # URL de retour si le collecteur annule.
        annulation = f'{base_frontend}/collecteur/paiements?paiement=annule'

        # ── Construit la description de l'article pour PayDunya ──
        type_dechet = vente.idTypeDechet.nom if vente.idTypeDechet else 'Déchet'
        citoyen_nom = ''
        if vente.idUtilisateur:
            citoyen_nom = (
                f'{vente.idUtilisateur.first_name} '
                f'{vente.idUtilisateur.last_name}'
            ).strip()

        # ── Construit la facture PayDunya ──
        facture = {
            'invoice': {
                'items': {
                    'vente_dechet': {
                        'name': (
                            f'Achat {type_dechet} — '
                            f'{vente.quantite} kg'
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
                # Canal de paiement sélectionné par le collecteur.
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
                'cancel_url':   annulation,
                'return_url':   retour,
                'callback_url': callback_url,
            },
            # Données personnalisées pour retrouver la vente dans l'IPN.
            'custom_data': {
                'reference': reference,
                'vente_id':  vente.idVente,
            },
        }

        # ── Appelle l'API PayDunya pour créer la facture ──
        try:
            resultat = appeler_paydunya(
                'checkout-invoice/create',
                method='POST',
                body=facture,
            )
        except PayDunyaError as error:
            return Response(
                {'detail': str(error)},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # ── Valide la réponse PayDunya ──
        token       = resultat.get('token')
        url_paiement = resultat.get('response_text')
        parsed_url  = urlparse(url_paiement) if isinstance(url_paiement, str) else None

        if (
            resultat.get('response_code') != '00'
            or not token
            or not parsed_url
            or parsed_url.scheme != 'https'
            or parsed_url.netloc not in {'app.paydunya.com', 'paydunya.com'}
        ):
            return Response(
                {
                    'detail': resultat.get(
                        'response_text',
                        'PayDunya n\'a pas créé la facture.'
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        # ── Enregistre la référence et le token PayDunya sur la vente ──
        vente.referencePaiement = reference
        vente.tokenPayDunya     = token
        vente.methodePaiement   = operateur.replace('_', ' ').title()
        vente.save(update_fields=[
            'referencePaiement',
            'tokenPayDunya',
            'methodePaiement',
        ])

        # ── Retourne la référence et l'URL de paiement au frontend ──
        return Response(
            {
                'reference':   reference,
                'urlPaiement': url_paiement,
            },
            status=status.HTTP_201_CREATED
        )


class VentePaiementVerifierView(APIView):
    """
    Vérifie le statut d'un paiement de vente auprès de PayDunya.
    Appelé par Angular après le retour depuis la page PayDunya
    (polling jusqu'à confirmation).

    URL    : GET /api/ventes/paiement/verifier/?reference=VP-xxx
    Retour : { "statutPaiement": "paye", "estPaye": true }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):

        # Récupère la référence depuis les query params.
        reference = request.query_params.get('reference', '').strip()

        if not reference:
            return Response(
                {'detail': 'Le paramètre reference est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Récupère le profil collecteur de l'utilisateur connecté.
        collecteur = Collecteur.objects.filter(
            idUtilisateur=request.user
        ).first()

        if not collecteur:
            return Response(
                {'detail': 'Profil collecteur introuvable.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Recherche la vente correspondant à la référence ET au collecteur.
        # Double vérification : seul le collecteur concerné peut vérifier.
        vente = VenteDechet.objects.filter(
            referencePaiement=reference,
            idCollecteur=collecteur,
        ).first()

        if not vente:
            return Response(
                {'detail': 'Référence de paiement introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Si la vente est déjà marquée payée en base, on répond directement
        # sans interroger PayDunya (optimisation).
        if vente.statutPaiement == 'paye':
            return Response({
                'statutPaiement': 'paye',
                'estPaye':        True,
            })

        # Interroge PayDunya pour obtenir le vrai statut de la facture.
        if not vente.tokenPayDunya:
            return Response(
                {'detail': 'Aucune facture PayDunya associée à cette vente.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            resultat = appeler_paydunya(
                f'checkout-invoice/confirm/{vente.tokenPayDunya}'
            )
        except PayDunyaError as error:
            return Response(
                {'detail': str(error)},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # Extrait les données de la facture depuis la réponse PayDunya.
        facture = resultat.get('data', resultat)
        est_paye = (
            facture.get('response_code') == '00'
            and str(facture.get('status', '')).lower() == 'completed'
        )

        if est_paye and vente.statutPaiement != 'paye':
            # Met à jour le statut en base et confirme le paiement.
            vente.statutPaiement = 'paye'
            vente.save(update_fields=['statutPaiement'])

        return Response({
            'statutPaiement': 'paye' if est_paye else vente.statutPaiement,
            'estPaye':        est_paye,
        })


class VentePaiementCallbackView(APIView):
    """
    Endpoint IPN (Instant Payment Notification) de PayDunya.
    PayDunya appelle cet endpoint automatiquement après confirmation
    du paiement, indépendamment du retour navigateur.

    URL             : POST /api/ventes/paiement/ipn/
    Authentification: aucune (AllowAny) — PayDunya n'envoie pas de JWT.
    """

    # Pas d'authentification JWT : c'est PayDunya qui appelle cet endpoint.
    authentication_classes = []
    permission_classes     = [AllowAny]

    def post(self, request):

        # PayDunya peut envoyer les données sous différentes structures.
        data    = request.data.get('data', request.data)
        invoice = data.get('invoice', {}) if isinstance(data, dict) else {}
        token   = (
            invoice.get('token') if isinstance(invoice, dict) else None
        ) or data.get('token')

        if not token:
            return Response(
                {'detail': 'Notification PayDunya invalide : token manquant.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Recherche la vente associée au token PayDunya.
        vente = VenteDechet.objects.filter(
            tokenPayDunya=token
        ).first()

        if not vente:
            # On retourne 200 même si la vente est inconnue pour que
            # PayDunya ne continue pas de renvoyer la notification.
            return Response({'received': True}, status=status.HTTP_200_OK)

        # Vérifie le statut réel auprès de PayDunya.
        try:
            resultat = appeler_paydunya(
                f'checkout-invoice/confirm/{vente.tokenPayDunya}'
            )
        except PayDunyaError:
            # En cas d'erreur temporaire, on retourne 200 pour éviter
            # les relances inutiles de PayDunya. Le polling frontend
            # rattrapera l'état.
            return Response({'received': True}, status=status.HTTP_200_OK)

        facture  = resultat.get('data', resultat)
        est_paye = (
            facture.get('response_code') == '00'
            and str(facture.get('status', '')).lower() == 'completed'
        )

        # Met à jour le statut en base si le paiement est confirmé.
        if est_paye and vente.statutPaiement != 'paye':
            vente.statutPaiement = 'paye'
            vente.save(update_fields=['statutPaiement'])

        return Response({'received': True}, status=status.HTTP_200_OK)
