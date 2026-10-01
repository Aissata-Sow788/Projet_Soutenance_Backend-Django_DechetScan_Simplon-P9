import json
import re
import uuid
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from collecte.models import PointCollecte
from users.permissions import IsAdmin
from .models import Collecteur, AbonnementCollecteur
from .serializers import (
    CollecteurSerializer,
    CollecteurCreationSerializer,
    CollecteurProfilSerializer,
    CollecteurValidationSerializer,
    AbonnementCollecteurSerializer,
    AbonnementCollecteurCreationSerializer,
    UtilisateurProfilCollecteurSerializer,
)


PAYDUNYA_API_BASE_URLS = {
    'test': 'https://app.paydunya.com/sandbox-api/v1',
    'live': 'https://app.paydunya.com/api/v1',
}
ABONNEMENT_PLANS = {
    'essentiel': {
        'label': 'Essentiel',
        'montant': 5000,
        'description': 'Pour les collecteurs indépendants.',
        'fonctionnalites': [
            'Recevoir des demandes',
            'Gérer les demandes',
            'Outil de planification',
            'Suivi des collectes',
        ],
    },
    'professionnel': {
        'label': 'Professionnel',
        'montant': 10000,
        'description': "L'offre la plus équilibrée.",
        'fonctionnalites': [
            'Tout le pack Essentiel',
            'Collectes illimitées',
            "Jusqu'à 5 zones",
            'Rapports analytiques',
        ],
    },
    'entreprise': {
        'label': 'Entreprise',
        'montant': 20000,
        'description': 'Solutions pour grandes flottes.',
        'fonctionnalites': [
            'Multi-comptes collecteurs',
            "API d'intégration",
            'Account Manager dédié',
            'Support sur site',
        ],
    },
}
OPERATEURS_PAIEMENT = {
    'paydunya': 'PayDunya',
    'wave': 'Wave',
    'orange_money': 'Orange Money',
}


class PayDunyaError(Exception):
    """Erreur explicite lors d'un appel au service de paiement PayDunya."""


def message_erreur_paydunya(error):
    try:
        contenu = json.loads(error.read().decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        contenu = {}

    message = ''
    if isinstance(contenu, dict):
        message = (
            contenu.get('response_text')
            or contenu.get('message')
            or contenu.get('detail')
            or ''
        )
    if not isinstance(message, str):
        message = ''
    message = re.sub(
        r'(?i)(master|private|token)[-_ ]?key["\s:=]+[^,\s"}]+',
        r'\1 key [masqué]',
        message,
    )
    message = ' '.join(message.split())[:240]

    if error.code == 403:
        conseil = (
            'Vérifiez dans le tableau de bord PayDunya que la Master Key, '
            'Private Key et Token viennent de la même application et du même '
            'mode que PAYDUNYA_MODE. Le tunnel ngrok ne cause pas ce refus : '
            'il sert uniquement au callback après le paiement.'
        )
    else:
        conseil = 'Vérifiez la configuration de votre application PayDunya.'

    if message:
        return f'PayDunya a refusé la requête (HTTP {error.code}) : {message} {conseil}'
    return f'PayDunya a refusé la requête (HTTP {error.code}). {conseil}'


def obtenir_url_callback_paydunya():
    if settings.PAYDUNYA_MODE == 'test':
        # On n'essaie de contacter ngrok que si l'URL est configurée.
        # En Docker, NGROK_AGENT_API_URL est vide → on saute directement
        # au fallback PAYDUNYA_CALLBACK_URL.
        ngrok_url = getattr(settings, 'NGROK_AGENT_API_URL', '') or ''
        if ngrok_url:
            try:
                with urlopen(ngrok_url, timeout=2) as response:
                    donnees = json.loads(response.read().decode('utf-8'))
            except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError):
                donnees = {}

            tunnels = donnees.get('tunnels', []) if isinstance(donnees, dict) else []
            for tunnel in tunnels:
                if not isinstance(tunnel, dict):
                    continue
                url_publique = tunnel.get('public_url', '')
                configuration = tunnel.get('config', {})
                if not isinstance(configuration, dict):
                    continue
                adresse_locale = configuration.get('addr', '')
                try:
                    adresse_locale = urlparse(adresse_locale)
                    url_publique = urlparse(url_publique)
                except (TypeError, ValueError):
                    continue
                if (
                    adresse_locale.port == 8000
                    and url_publique.scheme == 'https'
                    and url_publique.hostname
                ):
                    return f'{url_publique.geturl().rstrip("/")}/api/paydunya/ipn/'

    return settings.PAYDUNYA_CALLBACK_URL or None


def appeler_paydunya(path, method='GET', body=None):
    cles = {
        'PAYDUNYA-MASTER-KEY': settings.PAYDUNYA_MASTER_KEY,
        'PAYDUNYA-PRIVATE-KEY': settings.PAYDUNYA_PRIVATE_KEY,
        'PAYDUNYA-TOKEN': settings.PAYDUNYA_TOKEN,
    }
    if not all(cles.values()):
        raise PayDunyaError('La configuration PayDunya est incomplète.')
    base_url = PAYDUNYA_API_BASE_URLS.get(settings.PAYDUNYA_MODE)
    if not base_url:
        raise PayDunyaError('PAYDUNYA_MODE doit être « test » ou « live ».')

    request_body = json.dumps(body).encode('utf-8') if body is not None else None
    request = Request(
        f'{base_url}/{path}',
        data=request_body,
        headers={
            **cles,
            'Content-Type': 'application/json',
            # User-Agent obligatoire : sans lui, Cloudflare (qui protège
            # app.paydunya.com) retourne 403 error code 1010 même si les
            # clés sont correctes.
            'User-Agent': 'DechetScan/1.0 (+https://dechetscan.sn)',
            'Accept': 'application/json',
        },
        method=method,
    )

    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        raise PayDunyaError(message_erreur_paydunya(error)) from error
    except URLError as error:
        raise PayDunyaError(
            'PayDunya est momentanément injoignable.'
        ) from error
    except TimeoutError as error:
        raise PayDunyaError(
            'La requête vers PayDunya a expiré.'
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PayDunyaError(
            'La réponse PayDunya est illisible.'
        ) from error

    if not isinstance(result, dict):
        raise PayDunyaError('La réponse PayDunya est invalide.')
    return result


def obtenir_collecteur(request):
    return Collecteur.objects.filter(idUtilisateur=request.user).first()


def abonnement_actif(collecteur):
    return AbonnementCollecteur.objects.filter(
        idCollecteur=collecteur,
        statutPaiement='paye',
        dateFin__gte=timezone.localdate(),
    ).order_by('-dateFin').first()


class ProfilCollecteurView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def obtenir_profil(request, collecteur):
        utilisateur_serializer = UtilisateurProfilCollecteurSerializer(request.user)
        collecteur_serializer = CollecteurProfilSerializer(collecteur)
        return {
            'idCollecteur': collecteur.idCollecteur,
            **utilisateur_serializer.data,
            **collecteur_serializer.data,
            'nombrePointsGeres': PointCollecte.objects.filter(
                gerePar=request.user
            ).count(),
        }

    def get(self, request):
        collecteur = obtenir_collecteur(request)
        if collecteur is None:
            return Response(
                {'detail': 'Aucun profil collecteur n’est associé à ce compte.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(self.obtenir_profil(request, collecteur))

    def patch(self, request):
        collecteur = obtenir_collecteur(request)
        if collecteur is None:
            return Response(
                {'detail': 'Aucun profil collecteur n’est associé à ce compte.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        champs_utilisateur = {
            'first_name',
            'last_name',
            'email',
            'telephone',
            'ville',
        }
        donnees_utilisateur = {
            champ: request.data[champ]
            for champ in champs_utilisateur
            if champ in request.data
        }
        donnees_collecteur = {
            champ: request.data[champ]
            for champ in ('nomEntreprise', 'telephoneProfessionnel')
            if champ in request.data
        }
        utilisateur_serializer = UtilisateurProfilCollecteurSerializer(
            request.user,
            data=donnees_utilisateur,
            partial=True,
        )
        collecteur_serializer = CollecteurProfilSerializer(
            collecteur,
            data=donnees_collecteur,
            partial=True,
        )
        utilisateur_serializer.is_valid(raise_exception=True)
        collecteur_serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            utilisateur_serializer.save()
            collecteur_serializer.save()

        return Response(self.obtenir_profil(request, collecteur))


def confirmer_facture(abonnement):
    if not abonnement.tokenPayDunya:
        return False

    resultat = appeler_paydunya(
        f'checkout-invoice/confirm/{abonnement.tokenPayDunya}'
    )
    facture_confirmee = resultat.get('data', resultat)
    if (
        facture_confirmee.get('response_code') == '00'
        and str(facture_confirmee.get('status', '')).lower() == 'completed'
    ):
        if abonnement.statutPaiement == 'paye':
            return True
        aujourd_hui = timezone.localdate()
        abonnement.statutPaiement = 'paye'
        abonnement.dateDebut = aujourd_hui
        abonnement.dateFin = aujourd_hui + timedelta(days=30)
        abonnement.save(update_fields=[
            'statutPaiement',
            'dateDebut',
            'dateFin',
        ])
        return True
    return False


class PayDunyaPlansView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        offres = [
            {'code': code, **details, 'dureeJours': 30}
            for code, details in ABONNEMENT_PLANS.items()
        ]
        return Response(offres)


class AbonnementStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        collecteur = obtenir_collecteur(request)
        if not collecteur:
            return Response(
                {
                    'hasProfile': False,
                    'statutValidation': None,
                    'isActive': False,
                    'abonnement': None,
                },
                status=status.HTTP_200_OK,
            )

        abonnement = abonnement_actif(collecteur)
        return Response({
            'hasProfile': True,
            'statutValidation': collecteur.statutValidation,
            'isActive': abonnement is not None,
            'abonnement': {
                'idAbonnement': abonnement.idAbonnement,
                'plan': abonnement.plan,
                'montant': abonnement.montant,
                'dateFin': abonnement.dateFin,
            } if abonnement else None,
        })


class PayDunyaInvoiceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        collecteur = obtenir_collecteur(request)
        if not collecteur:
            return Response(
                {'detail': 'Créez votre profil collecteur avant de choisir une offre.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if abonnement_actif(collecteur):
            return Response(
                {'detail': 'Un abonnement est déjà actif sur ce compte collecteur.'},
                status=status.HTTP_409_CONFLICT,
            )

        plan = request.data.get('plan')
        operateur = request.data.get('operateur')
        if plan not in ABONNEMENT_PLANS:
            return Response(
                {'detail': 'La formule choisie est invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if operateur not in OPERATEURS_PAIEMENT:
            return Response(
                {'detail': 'L’opérateur de paiement choisi est invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
                    'Aucun callback public n’est configuré. Démarrez ngrok '
                    'avec « ngrok http 8000 », puis laissez '
                    'PAYDUNYA_CALLBACK_URL vide pour détecter son URL HTTPS.'
                )
            return Response(
                {
                    'detail': ' '.join(details),
                    'configurationManquante': configuration_manquante,
                    'callbackPublicDisponible': callback_url is not None,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        offre = ABONNEMENT_PLANS[plan]
        compte = collecteur.idUtilisateur
        client = {
            'name': f'{compte.first_name} {compte.last_name}'.strip(),
            'email': compte.email,
            'phone': compte.telephone or '',
        }
        reference = f'DS-{uuid.uuid4().hex}'
        aujourd_hui = timezone.localdate()
        abonnement = AbonnementCollecteur.objects.create(
            idCollecteur=collecteur,
            dateDebut=aujourd_hui,
            dateFin=aujourd_hui,
            statutPaiement='en_attente',
            methodePaiement=OPERATEURS_PAIEMENT[operateur],
            montant=offre['montant'],
            plan=plan,
            referencePaiement=reference,
        )
        base_frontend = settings.PAYDUNYA_FRONTEND_URL.rstrip('/')
        retour = f'{base_frontend}/collecteur/abonnement?reference={reference}'
        annulation = f'{base_frontend}/collecteur/abonnement?paiement=annule'
        facture = {
            'invoice': {
                'items': {
                    'abonnement': {
                        'name': f"Abonnement DechetScan - {offre['label']}",
                        'quantity': 1,
                        'unit_price': offre['montant'],
                        'total_price': offre['montant'],
                        'description': 'Accès collecteur pendant 30 jours.',
                    },
                },
                'total_amount': offre['montant'],
                'description': f"Abonnement collecteur {offre['label']} - {reference}",
                'customer': client,
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
                'subscription_id': abonnement.idAbonnement,
            },
        }
        canaux_operateur = {
            'wave': 'wave-senegal',
            'orange_money': 'orange-money-senegal',
        }
        if operateur in canaux_operateur:
            facture['invoice']['channels'] = canaux_operateur[operateur]

        try:
            resultat = appeler_paydunya(
                'checkout-invoice/create',
                method='POST',
                body=facture,
            )
        except PayDunyaError as error:
            abonnement.statutPaiement = 'echoue'
            abonnement.save(update_fields=['statutPaiement'])
            return Response(
                {'detail': str(error)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        token = resultat.get('token')
        url_paiement = resultat.get('response_text')
        parsed_url = urlparse(url_paiement) if isinstance(url_paiement, str) else None
        if (
            resultat.get('response_code') != '00'
            or not token
            or not parsed_url
            or parsed_url.scheme != 'https'
            or parsed_url.netloc not in {'app.paydunya.com', 'paydunya.com'}
        ):
            abonnement.statutPaiement = 'echoue'
            abonnement.save(update_fields=['statutPaiement'])
            return Response(
                {'detail': resultat.get('response_text', 'PayDunya n’a pas créé la facture.')},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        abonnement.tokenPayDunya = token
        abonnement.save(update_fields=['tokenPayDunya'])
        return Response({
            'reference': reference,
            'urlPaiement': url_paiement,
        }, status=status.HTTP_201_CREATED)


class PayDunyaVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reference = request.query_params.get('reference', '').strip()
        abonnement = AbonnementCollecteur.objects.filter(
            referencePaiement=reference,
            idCollecteur__idUtilisateur=request.user,
        ).first()
        if not abonnement:
            return Response(
                {'detail': 'Cette référence de paiement est introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            est_paye = confirmer_facture(abonnement)
        except PayDunyaError as error:
            return Response(
                {'detail': str(error)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        actif = abonnement_actif(abonnement.idCollecteur) is not None
        return Response({
            'statutPaiement': 'paye' if est_paye else abonnement.statutPaiement,
            'isActive': actif,
        })


class PayDunyaCallbackView(APIView):
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
        token = invoice.get('token') if isinstance(invoice, dict) else None
        token = token or data.get('token')
        if not token:
            return Response(
                {'detail': 'La notification ne contient pas de référence PayDunya.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        abonnement = AbonnementCollecteur.objects.filter(
            tokenPayDunya=token
        ).first()
        if not abonnement:
            return Response(
                {'detail': 'La facture PayDunya est inconnue.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            confirmer_facture(abonnement)
        except PayDunyaError as error:
            return Response(
                {'detail': str(error)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({'received': True}, status=status.HTTP_200_OK)


class CollecteurViewSet(viewsets.ModelViewSet):
    """
    Endpoints pour la gestion des collecteurs.

    - GET  /api/collecteurs/                    → liste tous les collecteurs (admin)
    - GET  /api/collecteurs/{id}/               → détail d'un collecteur (admin)
    - POST /api/collecteurs/                    → un utilisateur crée son profil collecteur
    - PATCH /api/collecteurs/{id}/valider/      → un admin valide ou rejette un collecteur
    - GET  /api/collecteurs/disponibles/        → liste les collecteurs disponibles pour une vente
                                                  Paramètres optionnels :
                                                  ?zone=Dakar (filtre par zoneIntervention)
    """

    queryset = Collecteur.objects.select_related('idUtilisateur').all()

    def get_serializer_class(self):
        # Lecture : utilise le serializer complet avec les infos utilisateur.
        if self.action in ['list', 'retrieve', 'disponibles']:
            return CollecteurSerializer

        # Validation/rejet : utilise le serializer dédié (un seul champ).
        if self.action == 'valider':
            return CollecteurValidationSerializer

        # Création : utilise le serializer simplifié (sans idUtilisateur).
        return CollecteurCreationSerializer

    def get_permissions(self):
        # Un utilisateur connecté peut créer son profil collecteur.
        if self.action == 'create':
            return [IsAuthenticated()]

        # L'endpoint disponibles est accessible à tout utilisateur connecté
        # (le citoyen en a besoin pour choisir à qui vendre ses déchets).
        if self.action == 'disponibles':
            return [IsAuthenticated()]

        # Toutes les autres actions sont réservées aux admins.
        return [IsAdmin()]

    def perform_create(self, serializer):
        """
        Associe automatiquement l'utilisateur connecté
        au profil collecteur qu'il crée.
        Retourne une erreur 400 claire si un profil existe déjà
        pour cet utilisateur (contrainte OneToOne).
        """
        if Collecteur.objects.filter(idUtilisateur=self.request.user).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                {'detail': 'Un profil collecteur existe déjà pour votre compte.'}
            )
        serializer.save(idUtilisateur=self.request.user)

    @action(detail=False, methods=['get'], url_path='disponibles')
    def disponibles(self, request):
        """
        Retourne la liste des collecteurs disponibles pour une vente de déchets.
        URL : GET /api/collecteurs/disponibles/
        Paramètres optionnels :
          ?zone=Dakar       → filtre par zoneIntervention (recherche partielle)

        Règles de filtrage :
        - Seuls les collecteurs avec statutValidation='valide' sont retournés.
        - Si le paramètre 'zone' est fourni, filtre sur zoneIntervention
          (insensible à la casse, recherche partielle).
        - idTypeDechet est accepté en paramètre pour la compatibilité frontend
          mais n'est pas utilisé côté filtre (pas de typesAcceptes sur Collecteur).

        Le frontend affiche la liste au citoyen pour qu'il choisisse
        à qui vendre ses déchets.
        """

        # Part des collecteurs validés uniquement.
        queryset = Collecteur.objects.select_related(
            'idUtilisateur'
        ).filter(
            statutValidation='valide'
        )

        # Filtre optionnel par zone d'intervention.
        # Le citoyen peut filtrer par sa zone pour voir les collecteurs proches.
        zone = request.query_params.get('zone', '').strip()
        if zone:
            queryset = queryset.filter(
                zoneIntervention__icontains=zone
            )

        # Sérialise et retourne la liste.
        serializer = CollecteurSerializer(queryset, many=True)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['patch'], permission_classes=[IsAdmin])
    def valider(self, request, pk=None):
        """
        Action personnalisée pour qu'un admin valide ou rejette un collecteur.
        URL : PATCH /api/collecteurs/{id}/valider/
        Corps attendu : { "statutValidation": "valide" } ou { "statutValidation": "rejete" }
        """
        collecteur = self.get_object()

        serializer = CollecteurValidationSerializer(
            collecteur,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                CollecteurSerializer(collecteur).data,
                status=status.HTTP_200_OK
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class AbonnementCollecteurViewSet(viewsets.ModelViewSet):
    """
    Endpoints pour la gestion des abonnements des collecteurs.

    - GET  /api/abonnements/         → liste tous les abonnements (admin)
    - GET  /api/abonnements/{id}/    → détail d'un abonnement (admin)
    - POST /api/abonnements/         → création manuelle réservée aux admins
    - POST /api/abonnements/initier-paiement/ → crée une facture PayDunya sécurisée
    """

    queryset = AbonnementCollecteur.objects.select_related('idCollecteur').all()

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return AbonnementCollecteurSerializer
        return AbonnementCollecteurCreationSerializer

    def get_permissions(self):
        return [IsAdmin()]

    def perform_create(self, serializer):
        """
        Associe automatiquement le profil collecteur
        de l'utilisateur connecté à l'abonnement créé.
        """
        collecteur = Collecteur.objects.get(idUtilisateur=self.request.user)
        serializer.save(idCollecteur=collecteur)
