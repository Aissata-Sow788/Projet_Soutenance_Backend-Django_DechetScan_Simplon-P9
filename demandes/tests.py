from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from collecteurs.models import Collecteur
from dechets.models import TypeDechet
from .models import DemandeCollecte


class DemandeCollecteWorkflowTests(TestCase):
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
        self.demande = DemandeCollecte.objects.create(
            idUtilisateur=self.citoyen,
            idTypeDechet=self.type_dechet,
            quantite=10,
            quartier='Plateau',
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
