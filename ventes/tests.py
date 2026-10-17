from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from collecteurs.models import Collecteur
from dechets.models import PanierDechet, PrixDechet, TypeDechet
from .models import VenteDechet


class VenteMultiPanierTests(TestCase):
    """Vérifie le calcul serveur du prix et la réservation des stocks."""

    def setUp(self):
        user_model = get_user_model()
        self.citoyen = user_model.objects.create_user(
            email='citoyen-vente@example.com',
            password='MotDePasseSecurise123!',
        )
        collecteur_user = user_model.objects.create_user(
            email='collecteur-vente@example.com',
            password='MotDePasseSecurise123!',
        )
        self.collecteur = Collecteur.objects.create(
            idUtilisateur=collecteur_user,
            statutValidation='valide',
        )
        autre_collecteur_user = user_model.objects.create_user(
            email='autre-collecteur-vente@example.com',
            password='MotDePasseSecurise123!',
        )
        self.autre_collecteur = Collecteur.objects.create(
            idUtilisateur=autre_collecteur_user,
            statutValidation='valide',
        )
        self.plastique = TypeDechet.objects.create(
            nom='Plastique',
            description='Déchets plastiques',
        )
        self.verre = TypeDechet.objects.create(
            nom='Verre',
            description='Déchets en verre',
        )
        self.panier_plastique = PanierDechet.objects.create(
            idUtilisateur=self.citoyen,
            idTypeDechet=self.plastique,
            nombreDisponible=10,
        )
        self.panier_verre = PanierDechet.objects.create(
            idUtilisateur=self.citoyen,
            idTypeDechet=self.verre,
            nombreDisponible=5,
        )
        aujourd_hui = timezone.localdate()
        PrixDechet.objects.create(
            idTypeDechet=self.plastique,
            idCollecteur=self.collecteur,
            prixParKg=100,
            commission=0,
            dateDebut=aujourd_hui - timedelta(days=1),
        )
        PrixDechet.objects.create(
            idTypeDechet=self.verre,
            idCollecteur=self.collecteur,
            prixParKg=50,
            commission=0,
            dateDebut=aujourd_hui - timedelta(days=1),
        )
        PrixDechet.objects.create(
            idTypeDechet=self.plastique,
            idCollecteur=self.autre_collecteur,
            prixParKg=900,
            commission=0,
            dateDebut=aujourd_hui - timedelta(days=1),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.citoyen)

    def test_create_sale_with_multiple_baskets_uses_server_prices_and_reserves_stock(self):
        """Les prix envoyés par le client sont ignorés au profit du référentiel."""
        response = self.client.post(
            '/api/ventes/',
            {
                'idCollecteur': self.collecteur.pk,
                'details': [
                    {
                        'idPanier': self.panier_plastique.pk,
                        'nombreObjets': 2,
                        'poidsKg': '0.500',
                    },
                    {
                        'idPanier': self.panier_verre.pk,
                        'nombreObjets': 3,
                        'poidsKg': '3.000',
                    },
                ],
                'prixPaye': '1.00',
                'methodePaiement': 'Wave',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data['details']), 2)
        self.assertEqual(Decimal(response.data['prixPaye']), Decimal('200.00'))
        self.panier_plastique.refresh_from_db()
        self.panier_verre.refresh_from_db()
        self.assertEqual(self.panier_plastique.nombreDisponible, 8)
        self.assertEqual(self.panier_verre.nombreDisponible, 2)
        self.assertEqual(response.data['details'][0]['nombreObjets'], 2)
        self.assertEqual(response.data['details'][0]['poidsKg'], '0.500')
        self.assertEqual(Decimal(response.data['poidsTotalKg']), Decimal('3.500'))

    def test_create_sale_rejects_insufficient_stock_without_partial_reservation(self):
        """Une ligne en rupture annule toute la vente et toute réservation partielle."""
        response = self.client.post(
            '/api/ventes/',
            {
                'idCollecteur': self.collecteur.pk,
                'details': [
                    {
                        'idPanier': self.panier_plastique.pk,
                        'nombreObjets': 2,
                        'poidsKg': '2',
                    },
                    {
                        'idPanier': self.panier_verre.pk,
                        'nombreObjets': 6,
                        'poidsKg': '6',
                    },
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(VenteDechet.objects.count(), 0)
        self.panier_plastique.refresh_from_db()
        self.panier_verre.refresh_from_db()
        self.assertEqual(self.panier_plastique.nombreDisponible, 10)
        self.assertEqual(self.panier_verre.nombreDisponible, 5)
