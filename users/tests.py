from types import SimpleNamespace

from django.test import TestCase
from rest_framework.test import APIClient
from .models import Utilisateur
from .serializers import (
    ChangementMotDePasseSerializer,
    ConnexionSerializer,
    ProfilUtilisateurModificationSerializer,
)


class ConnexionSerializerTests(TestCase):
    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            email='citoyen@example.com',
            password='TestPass123!',
            telephone='+221 77 123 45 67'
        )

    def test_login_accepts_phone_with_different_format(self):
        serializer = ConnexionSerializer(data={
            'identifiant': '771234567',
            'password': 'TestPass123!',
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn('access', serializer.validated_data)
        self.assertIn('refresh', serializer.validated_data)

    def test_login_email_is_case_insensitive(self):
        serializer = ConnexionSerializer(data={
            'identifiant': 'CITOYEN@EXAMPLE.COM',
            'password': 'TestPass123!',
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_disabled_user_cannot_receive_tokens(self):
        self.utilisateur.is_active = False
        self.utilisateur.save(update_fields=['is_active'])
        serializer = ConnexionSerializer(data={
            'identifiant': 'citoyen@example.com',
            'password': 'TestPass123!',
        })

        self.assertFalse(serializer.is_valid())
        self.assertNotIn('access', serializer.validated_data)

    def test_password_validation_errors_are_in_french(self):
        serializer = ChangementMotDePasseSerializer(
            data={
                'ancienMotDePasse': 'TestPass123!',
                'nouveauMotDePasse': 'qwerty123',
                'confirmationMotDePasse': 'qwerty123',
            },
            context={'request': SimpleNamespace(user=self.utilisateur)},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn(
            'trop courant',
            str(serializer.errors['nouveauMotDePasse'][0]).lower(),
        )

    def test_profile_serializer_accepts_personal_information(self):
        serializer = ProfilUtilisateurModificationSerializer(
            self.utilisateur,
            data={
                'first_name': 'Aissata',
                'last_name': 'Sow',
                'ville': 'Dakar',
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        utilisateur = serializer.save()
        self.assertEqual(utilisateur.first_name, 'Aissata')
        self.assertEqual(utilisateur.last_name, 'Sow')
        self.assertEqual(utilisateur.ville, 'Dakar')

    def test_profile_serializer_converts_an_empty_phone_to_null(self):
        serializer = ProfilUtilisateurModificationSerializer(
            self.utilisateur,
            data={'telephone': ''},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.save().telephone)

    def test_authenticated_user_can_update_own_profile(self):
        client = APIClient()
        client.force_authenticate(user=self.utilisateur)

        response = client.patch(
            '/api/auth/me/',
            {'first_name': 'Aissata', 'ville': 'Dakar'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['first_name'], 'Aissata')
        self.assertEqual(response.data['ville'], 'Dakar')
