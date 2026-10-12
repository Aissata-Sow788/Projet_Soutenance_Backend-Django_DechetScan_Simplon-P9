from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from collecteurs.models import Collecteur

from .models import PanierDechet, PrixDechet, TypeDechet


class PanierDechetApiTests(TestCase):
    """Vérifie le compte d'objets et l'isolation des paniers entre citoyens."""

    def setUp(self):
        user_model = get_user_model()
        self.citoyen = user_model.objects.create_user(
            email='citoyen-stock@example.com',
            password='MotDePasseSecurise123!',
        )
        self.autre_citoyen = user_model.objects.create_user(
            email='autre-stock@example.com',
            password='MotDePasseSecurise123!',
        )
        self.plastique = TypeDechet.objects.create(
            nom='Plastique',
            description='Déchets plastiques',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.citoyen)

    def test_additions_accumulate_in_one_private_basket(self):
        """Deux ajouts de plastique doivent alimenter le même panier."""
        premiere_reponse = self.client.post(
            '/api/paniers/',
            {
                'idTypeDechet': self.plastique.pk,
                'nombreDisponible': 2,
            },
            format='json',
        )
        self.assertEqual(premiere_reponse.status_code, 201, premiere_reponse.data)

        deuxieme_reponse = self.client.post(
            '/api/paniers/',
            {
                'idTypeDechet': self.plastique.pk,
                'nombreDisponible': 1,
            },
            format='json',
        )
        self.assertEqual(deuxieme_reponse.status_code, 201, deuxieme_reponse.data)
        self.assertEqual(PanierDechet.objects.filter(
            idUtilisateur=self.citoyen,
            idTypeDechet=self.plastique,
        ).count(), 1)
        panier = PanierDechet.objects.get(idUtilisateur=self.citoyen)
        self.assertEqual(panier.nombreDisponible, 3)
        self.assertEqual(panier.unite, 'objet')

        self.client.force_authenticate(self.autre_citoyen)
        response = self.client.get('/api/paniers/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_patch_replaces_the_object_count(self):
        """La modification du panier remplace le compte par le nouveau total."""
        panier = PanierDechet.objects.create(
            idUtilisateur=self.citoyen,
            idTypeDechet=self.plastique,
            nombreDisponible=2,
        )

        response = self.client.patch(
            f'/api/paniers/{panier.pk}/',
            {'nombreDisponible': 1},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        panier.refresh_from_db()
        self.assertEqual(panier.nombreDisponible, 1)


class PrixDechetCollecteurApiTests(TestCase):
    """Vérifie l'isolation des tarifs et leur gestion par le collecteur propriétaire."""

    def setUp(self):
        user_model = get_user_model()
        self.collecteur_user = user_model.objects.create_user(
            email='collecteur-tarifs@example.com',
            password='MotDePasseSecurise123!',
        )
        self.autre_collecteur_user = user_model.objects.create_user(
            email='autre-collecteur-tarifs@example.com',
            password='MotDePasseSecurise123!',
        )
        self.citoyen = user_model.objects.create_user(
            email='citoyen-tarifs@example.com',
            password='MotDePasseSecurise123!',
        )
        self.collecteur = Collecteur.objects.create(
            idUtilisateur=self.collecteur_user,
            nomEntreprise='Collecteur A',
            statutValidation='valide',
        )
        self.autre_collecteur = Collecteur.objects.create(
            idUtilisateur=self.autre_collecteur_user,
            nomEntreprise='Collecteur B',
            statutValidation='valide',
        )
        self.plastique = TypeDechet.objects.create(nom='Plastique')
        self.client = APIClient()

    def test_collecteur_creates_and_lists_only_its_own_tariffs(self):
        """Un tarif créé par le collecteur appartient à son profil et reste privé."""
        self.client.force_authenticate(self.collecteur_user)
        response = self.client.post(
            '/api/prix-dechets/',
            {
                'idTypeDechet': self.plastique.pk,
                'prixParKg': 75,
                'commission': 0,
                'dateDebut': '2026-10-08',
                'dateFin': None,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['idCollecteur'], self.collecteur.pk)
        self.assertEqual(response.data['nomTypeDechet'], 'Plastique')
        self.assertEqual(len(self.client.get('/api/prix-dechets/').data), 1)

        self.client.force_authenticate(self.autre_collecteur_user)
        self.assertEqual(self.client.get('/api/prix-dechets/').data, [])

    def test_collecteur_cannot_modify_another_collectors_tariff(self):
        """Un tarif d'un autre propriétaire est masqué sur retrieve et update."""
        tarif = PrixDechet.objects.create(
            idTypeDechet=self.plastique,
            idCollecteur=self.autre_collecteur,
            prixParKg=50,
            commission=0,
            dateDebut='2026-10-08',
        )
        self.client.force_authenticate(self.collecteur_user)

        response = self.client.patch(
            f'/api/prix-dechets/{tarif.pk}/',
            {'prixParKg': 100},
            format='json',
        )

        self.assertEqual(response.status_code, 404)
        tarif.refresh_from_db()
        self.assertEqual(tarif.prixParKg, 50)

    def test_citizen_can_request_tariffs_for_a_selected_collector(self):
        """La vente citoyenne peut afficher les tarifs du collecteur choisi."""
        tarif = PrixDechet.objects.create(
            idTypeDechet=self.plastique,
            idCollecteur=self.collecteur,
            prixParKg=75,
            commission=0,
            dateDebut='2026-10-08',
        )
        PrixDechet.objects.create(
            idTypeDechet=self.plastique,
            idCollecteur=self.autre_collecteur,
            prixParKg=100,
            commission=0,
            dateDebut='2026-10-08',
        )
        self.client.force_authenticate(self.citoyen)

        response = self.client.get(
            f'/api/prix-dechets/?idCollecteur={self.collecteur.pk}'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['idPrix'] for item in response.data], [tarif.pk])

    def test_anonymous_tariff_list_does_not_fail(self):
        """La liste publique historique reste accessible sans profil collecteur."""
        response = APIClient().get('/api/prix-dechets/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, [])
