from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient
import requests

from dechets.models import PanierDechet, TypeDechet
from scans.models import ScanDechet


class ScanPanierIntegrationTests(TestCase):
    """Vérifie qu'une catégorie détectée crée un panier vide pour le citoyen."""

    def setUp(self):
        self.temp_media = TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)

        self.citoyen = get_user_model().objects.create_user(
            email='citoyen-scan@example.com',
            password='MotDePasseSecurise123!',
        )
        self.plastique, _ = TypeDechet.objects.get_or_create(
            nom='Plastique',
            defaults={'description': 'Déchets plastiques'},
        )
        self.client = APIClient()
        self.client.force_authenticate(self.citoyen)

    @staticmethod
    def image_upload():
        contenu = BytesIO()
        Image.new('RGB', (1, 1), color='white').save(contenu, format='PNG')
        return SimpleUploadedFile(
            'scan.png',
            contenu.getvalue(),
            content_type='image/png',
        )

    @patch('scans.views.creer_notification_apres_scan')
    @patch(
        'scans.views.analyser_photo_avec_ia',
        return_value={
            'dechets': [
                {
                    'categorie': 'Plastique',
                    'objet': 'Bouteille',
                    'confiance': 0.95,
                },
            ],
        },
    )
    def test_detected_category_creates_one_empty_basket_for_citizen(
        self,
        analyser,
        notifier,
    ):
        response = self.client.post(
            '/api/scans/',
            {'photoUrl': self.image_upload()},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['idUtilisateur'], self.citoyen.pk)
        self.assertEqual(
            len(response.data['analyseIA']['detections']),
            1,
            response.data,
        )
        panier = PanierDechet.objects.get(
            idUtilisateur=self.citoyen,
            idTypeDechet=self.plastique,
        )
        self.assertEqual(panier.nombreDisponible, 0)
        self.assertEqual(panier.unite, 'objet')
        self.assertEqual(response.data['analyseIA']['detections'][0]['objet'], 'Bouteille')

    @patch(
        'scans.views.analyser_photo_avec_ia',
        side_effect=requests.HTTPError('503 Service Unavailable'),
    )
    def test_unavailable_ai_service_returns_503_and_removes_incomplete_scan(
        self,
        analyser,
    ):
        response = self.client.post(
            '/api/scans/',
            {'photoUrl': self.image_upload()},
            format='multipart',
        )

        self.assertEqual(response.status_code, 503, response.data)
        self.assertIn('temporairement indisponible', response.data['detail'])
        self.assertEqual(ScanDechet.objects.count(), 0)
