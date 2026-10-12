from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from collecteurs.models import Collecteur
from dechets.models import PanierDechet, TypeDechet
from scans.models import AnalyseIA, DetectionIA, ScanDechet
from .models import DetailDemandeCollecte, DemandeCollecte


class DemandeCollecteWorkflowTests(TestCase):
    """Couvre les transitions d'état et les réservations multi-paniers."""

    def setUp(self):
        user_model = get_user_model()
        self.citoyen = user_model.objects.create_user(
            email='citoyen@example.com',
            password='MotDePasseSecurise123!',
        )
        self.collecteur_un_user = user_model.objects.create_user(
            email='collecteur1@example.com',
            password='MotDePasseSecurise123!',
        )
        self.collecteur_deux_user = user_model.objects.create_user(
            email='collecteur2@example.com',
            password='MotDePasseSecurise123!',
        )
        self.collecteur_un = Collecteur.objects.create(
            idUtilisateur=self.collecteur_un_user,
            statutValidation='valide',
        )
        self.collecteur_deux = Collecteur.objects.create(
            idUtilisateur=self.collecteur_deux_user,
            statutValidation='valide',
        )
        self.type_dechet = TypeDechet.objects.create(
            nom='Plastique',
            description='Déchets plastiques',
        )
        self.panier = PanierDechet.objects.create(
            idUtilisateur=self.citoyen,
            idTypeDechet=self.type_dechet,
            nombreDisponible=0,
        )
        self.demande = DemandeCollecte.objects.create(
            idUtilisateur=self.citoyen,
            quartier='Plateau',
        )
        DetailDemandeCollecte.objects.create(
            idDemande=self.demande,
            idPanier=self.panier,
            poidsKg=10,
            nombreObjets=None,
        )
        self.client = APIClient()

    def test_refusal_hides_request_only_from_refusing_collector(self):
        self.client.force_authenticate(self.collecteur_un_user)

        response = self.client.post(
            f'/api/demandes/{self.demande.idDemande}/refuser/'
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.demande.statut, 'en_attente')

        response = self.client.get('/api/demandes/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        self.client.force_authenticate(self.collecteur_deux_user)
        response = self.client.get('/api/demandes/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item['idDemande'] for item in response.data],
            [self.demande.idDemande],
        )

    def test_only_first_collector_can_accept_and_then_update_status(self):
        self.client.force_authenticate(self.collecteur_un_user)
        response = self.client.patch(
            f'/api/demandes/{self.demande.idDemande}/accepter/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['statut'], 'acceptee')
        self.assertEqual(
            response.data['collecteurAttribue']['idCollecteur'],
            self.collecteur_un.pk,
        )

        self.client.force_authenticate(self.collecteur_deux_user)
        response = self.client.patch(
            f'/api/demandes/{self.demande.idDemande}/accepter/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, 409)

        self.client.force_authenticate(self.collecteur_un_user)
        response = self.client.patch(
            f'/api/demandes/{self.demande.idDemande}/statut/',
            {'statut': 'en_cours'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['statut'], 'en_cours')

        response = self.client.patch(
            f'/api/demandes/{self.demande.idDemande}/statut/',
            {'statut': 'terminee'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['statut'], 'terminee')

    def test_collector_cannot_skip_or_reverse_status_transitions(self):
        self.demande.collecteurAttribue = self.collecteur_un
        self.demande.statut = 'acceptee'
        self.demande.save(update_fields=['collecteurAttribue', 'statut'])
        self.client.force_authenticate(self.collecteur_un_user)

        response = self.client.patch(
            f'/api/demandes/{self.demande.idDemande}/statut/',
            {'statut': 'terminee'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)

    def test_request_detail_includes_only_matching_prior_scan_photos(self):
        scan = ScanDechet.objects.create(
            idUtilisateur=self.citoyen,
            photoUrl='scans/plastique.jpg',
        )
        ScanDechet.objects.filter(pk=scan.pk).update(
            dateScan=self.demande.dateDemande - timedelta(seconds=1),
        )
        analyse = AnalyseIA.objects.create(idScan=scan)
        DetectionIA.objects.create(
            objet='Bouteille',
            confiance=0.98,
            idAnalyse=analyse,
            idTypeDechet=self.type_dechet,
        )

        autre_type = TypeDechet.objects.create(
            nom='Verre',
            description='Déchets en verre',
        )
        scan_autre_categorie = ScanDechet.objects.create(
            idUtilisateur=self.citoyen,
            photoUrl='scans/verre.jpg',
        )
        analyse_autre_categorie = AnalyseIA.objects.create(
            idScan=scan_autre_categorie,
        )
        DetectionIA.objects.create(
            objet='Bouteille',
            confiance=0.95,
            idAnalyse=analyse_autre_categorie,
            idTypeDechet=autre_type,
        )

        self.client.force_authenticate(self.collecteur_un_user)
        response = self.client.get(f'/api/demandes/{self.demande.idDemande}/')

        self.assertEqual(response.status_code, 200)
        photos = response.data['details'][0]['photos']
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0]['idScan'], scan.idScan)
        self.assertTrue(photos[0]['photoUrl'].endswith('/media/scans/plastique.jpg'))

    def test_multibasket_request_reserves_stock_and_cancellation_restores_once(self):
        """La demande réserve chaque catégorie et l'annulation rend le stock une fois."""
        autre_type = TypeDechet.objects.create(
            nom='Verre',
            description='Déchets en verre',
        )
        autre_panier = PanierDechet.objects.create(
            idUtilisateur=self.citoyen,
            idTypeDechet=autre_type,
            nombreDisponible=4,
        )
        self.panier.nombreDisponible = 8
        self.panier.save(update_fields=['nombreDisponible'])
        self.client.force_authenticate(self.citoyen)

        response = self.client.post(
            '/api/demandes/',
            {
                'details': [
                    {'idPanier': self.panier.pk, 'nombreObjets': 3, 'poidsKg': '3.500'},
                    {'idPanier': autre_panier.pk, 'nombreObjets': 2, 'poidsKg': '2.000'},
                ],
                'quartier': 'Plateau',
                'typeDemande': 'ramassage',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data['details']), 2)
        demande_id = response.data['idDemande']
        self.panier.refresh_from_db()
        autre_panier.refresh_from_db()
        self.assertEqual(self.panier.nombreDisponible, 5)
        self.assertEqual(autre_panier.nombreDisponible, 2)
        self.assertEqual(response.data['details'][0]['poidsKg'], '3.500')
        self.assertEqual(response.data['nombreObjets'], 5)
        self.assertEqual(Decimal(response.data['poidsTotalKg']), Decimal('5.500'))

        admin = get_user_model().objects.create_user(
            email='admin@example.com',
            password='MotDePasseSecurise123!',
            role='admin',
        )
        self.client.force_authenticate(admin)
        response = self.client.patch(
            f'/api/demandes/{demande_id}/statut/',
            {'statut': 'annulee'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.panier.refresh_from_db()
        autre_panier.refresh_from_db()
        self.assertEqual(self.panier.nombreDisponible, 8)
        self.assertEqual(autre_panier.nombreDisponible, 4)

        response = self.client.patch(
            f'/api/demandes/{demande_id}/statut/',
            {'statut': 'annulee'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.panier.refresh_from_db()
        self.assertEqual(self.panier.nombreDisponible, 8)

    def test_request_rejects_quantities_above_available_stock(self):
        """Une demande trop grande échoue sans créer d'opération ni modifier le stock."""
        self.panier.nombreDisponible = 1
        self.panier.save(update_fields=['nombreDisponible'])
        self.client.force_authenticate(self.citoyen)

        response = self.client.post(
            '/api/demandes/',
            {
                'details': [{
                    'idPanier': self.panier.pk,
                    'nombreObjets': 2,
                    'poidsKg': '1.000',
                }],
                'quartier': 'Plateau',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(DemandeCollecte.objects.filter(
            idUtilisateur=self.citoyen,
            quartier='Plateau',
            dateSouhaitee__isnull=True,
        ).exclude(pk=self.demande.pk).exists())
        self.panier.refresh_from_db()
        self.assertEqual(self.panier.nombreDisponible, 1)

    def test_cancelling_historical_request_does_not_invent_object_count(self):
        """Une ancienne demande sans compteur ne recrédite pas son poids en objets."""
        self.panier.nombreDisponible = 5
        self.panier.save(update_fields=['nombreDisponible'])
        admin = get_user_model().objects.create_user(
            email='admin-historique@example.com',
            password='MotDePasseSecurise123!',
            role='admin',
        )
        self.client.force_authenticate(admin)

        response = self.client.patch(
            f'/api/demandes/{self.demande.idDemande}/statut/',
            {'statut': 'annulee'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.panier.refresh_from_db()
        self.assertEqual(self.panier.nombreDisponible, 5)
