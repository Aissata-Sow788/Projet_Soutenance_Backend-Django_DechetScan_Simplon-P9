from datetime import date
import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .views import (
    AbonnementStatusView,
    PayDunyaInvoiceView,
    PayDunyaPlansView,
    appeler_paydunya,
    confirmer_facture,
    message_erreur_paydunya,
    obtenir_url_callback_paydunya,
)


class AbonnementStatusTests(SimpleTestCase):
    def test_missing_profile_is_reported_explicitly_without_a_not_found_error(self):
        request = APIRequestFactory().get('/api/abonnements/statut/')
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True))

        with patch('collecteurs.views.obtenir_collecteur', return_value=None):
            response = AbonnementStatusView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {
            'hasProfile': False,
            'statutValidation': None,
            'isActive': False,
            'abonnement': None,
        })

    def test_profile_without_active_subscription_is_not_reported_as_missing(self):
        collecteur = SimpleNamespace(statutValidation='valide')
        request = APIRequestFactory().get('/api/abonnements/statut/')
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True))

        with (
            patch('collecteurs.views.obtenir_collecteur', return_value=collecteur),
            patch('collecteurs.views.abonnement_actif', return_value=None),
        ):
            response = AbonnementStatusView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['hasProfile'])
        self.assertFalse(response.data['isActive'])
        self.assertIsNone(response.data['abonnement'])


class PayDunyaSubscriptionTests(SimpleTestCase):
    def test_monthly_prices_are_exposed_by_the_api(self):
        request = APIRequestFactory().get('/api/abonnements/offres/')
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True))

        response = PayDunyaPlansView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {offre['code']: offre['montant'] for offre in response.data},
            {
                'essentiel': 5000,
                'professionnel': 10000,
                'entreprise': 20000,
            },
        )
        self.assertTrue(all(offre['dureeJours'] == 30 for offre in response.data))

    @override_settings(
        PAYDUNYA_MASTER_KEY='master',
        PAYDUNYA_PRIVATE_KEY='private',
        PAYDUNYA_TOKEN='token',
        PAYDUNYA_MODE='test',
    )
    @patch('collecteurs.views.urlopen')
    def test_test_mode_uses_paydunya_sandbox_endpoint(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'response_code': '00',
        }).encode()
        urlopen.return_value = response

        appeler_paydunya('checkout-invoice/create', method='POST', body={})

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            'https://app.paydunya.com/sandbox-api/v1/checkout-invoice/create',
        )

    def test_forbidden_response_includes_safe_provider_reason_and_actionable_advice(self):
        error = HTTPError(
            'https://app.paydunya.com/sandbox-api/v1/checkout-invoice/create',
            403,
            'Forbidden',
            {},
            BytesIO(json.dumps({
                'response_text': 'Integration credentials are not authorized.',
            }).encode()),
        )

        message = message_erreur_paydunya(error)

        self.assertIn('HTTP 403', message)
        self.assertIn('Integration credentials are not authorized.', message)
        self.assertIn('même application', message)
        self.assertIn('ngrok ne cause pas ce refus', message)

    def test_forbidden_response_masks_any_credential_like_content(self):
        error = HTTPError(
            'https://app.paydunya.com/sandbox-api/v1/checkout-invoice/create',
            403,
            'Forbidden',
            {},
            BytesIO(json.dumps({
                'message': 'Private Key: secret-value is invalid',
            }).encode()),
        )

        message = message_erreur_paydunya(error)

        self.assertNotIn('secret-value', message)
        self.assertIn('[masqué]', message)

    @override_settings(PAYDUNYA_CALLBACK_URL='https://public.example/callback/')
    @patch('collecteurs.views.urlopen')
    def test_ngrok_callback_is_preferred_to_static_url_in_test_mode(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'tunnels': [{
                'public_url': 'https://example.ngrok-free.app',
                'config': {'addr': 'http://localhost:8000'},
            }],
        }).encode()
        urlopen.return_value = response

        callback = obtenir_url_callback_paydunya()

        self.assertEqual(
            callback,
            'https://example.ngrok-free.app/api/paydunya/ipn/',
        )

    @override_settings(PAYDUNYA_CALLBACK_URL='')
    @patch('collecteurs.views.urlopen')
    def test_ngrok_callback_is_discovered_for_the_django_tunnel(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'tunnels': [
                {
                    'public_url': 'http://example.ngrok-free.app',
                    'config': {'addr': 'http://localhost:4200'},
                },
                {
                    'public_url': 'https://example.ngrok-free.app',
                    'config': {'addr': 'http://localhost:8000'},
                },
            ],
        }).encode()
        urlopen.return_value = response

        callback = obtenir_url_callback_paydunya()

        self.assertEqual(
            callback,
            'https://example.ngrok-free.app/api/paydunya/ipn/',
        )

    @override_settings(
        PAYDUNYA_MODE='live',
        PAYDUNYA_CALLBACK_URL='https://public.example/callback/',
    )
    @patch('collecteurs.views.urlopen')
    def test_production_uses_static_callback_without_querying_local_ngrok(self, urlopen):
        callback = obtenir_url_callback_paydunya()

        self.assertEqual(callback, 'https://public.example/callback/')
        urlopen.assert_not_called()

    @override_settings(PAYDUNYA_CALLBACK_URL='')
    @patch('collecteurs.views.urlopen')
    def test_no_ngrok_callback_is_reported_as_a_missing_public_callback(self, urlopen):
        urlopen.side_effect = URLError('ngrok agent unavailable')
        request = APIRequestFactory().post(
            '/api/abonnements/initier-paiement/',
            {'plan': 'essentiel', 'operateur': 'paydunya'},
            format='json',
        )
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True))

        with (
            patch(
                'collecteurs.views.obtenir_collecteur',
                return_value=SimpleNamespace(idUtilisateur=SimpleNamespace()),
            ),
            patch('collecteurs.views.abonnement_actif', return_value=None),
            override_settings(
                PAYDUNYA_MASTER_KEY='master',
                PAYDUNYA_PRIVATE_KEY='private',
                PAYDUNYA_TOKEN='token',
            ),
        ):
            response = PayDunyaInvoiceView.as_view()(request)

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.data['callbackPublicDisponible'])
        self.assertIn('ngrok http 8000', response.data['detail'])

    @override_settings(
        PAYDUNYA_MASTER_KEY='',
        PAYDUNYA_PRIVATE_KEY='',
        PAYDUNYA_TOKEN='',
        PAYDUNYA_CALLBACK_URL='',
    )
    @patch('collecteurs.views.urlopen', side_effect=URLError('ngrok agent unavailable'))
    @patch('collecteurs.views.abonnement_actif', return_value=None)
    @patch(
        'collecteurs.views.obtenir_collecteur',
        return_value=SimpleNamespace(idUtilisateur=SimpleNamespace()),
    )
    def test_invoice_endpoint_explains_missing_paydunya_configuration(
        self,
        _collecteur,
        _abonnement,
        _ngrok_agent,
    ):
        request = APIRequestFactory().post(
            '/api/abonnements/initier-paiement/',
            {'plan': 'essentiel', 'operateur': 'paydunya'},
            format='json',
        )
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True))

        response = PayDunyaInvoiceView.as_view()(request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.data['configurationManquante'],
            [
                'PAYDUNYA_MASTER_KEY',
                'PAYDUNYA_PRIVATE_KEY',
                'PAYDUNYA_TOKEN',
            ],
        )
        self.assertFalse(response.data['callbackPublicDisponible'])
        self.assertIn('ngrok http 8000', response.data['detail'])

    @patch('collecteurs.views.appeler_paydunya')
    @patch('collecteurs.views.timezone.localdate', return_value=date(2026, 9, 26))
    def test_only_a_server_confirmed_invoice_activates_the_subscription(
        self,
        _today,
        paydunya,
    ):
        paydunya.return_value = {
            'data': {
                'response_code': '00',
                'status': 'completed',
            },
        }
        abonnement = SimpleNamespace(
            tokenPayDunya='paydunya-token',
            statutPaiement='en_attente',
            dateDebut=date(2026, 9, 26),
            dateFin=date(2026, 9, 26),
            save=Mock(),
        )

        self.assertTrue(confirmer_facture(abonnement))

        self.assertEqual(abonnement.statutPaiement, 'paye')
        self.assertEqual(abonnement.dateDebut, date(2026, 9, 26))
        self.assertEqual(abonnement.dateFin, date(2026, 10, 26))
        abonnement.save.assert_called_once()

    @patch('collecteurs.views.appeler_paydunya')
    def test_pending_invoice_does_not_activate_subscription(self, paydunya):
        paydunya.return_value = {
            'response_code': '00',
            'status': 'pending',
        }
        abonnement = SimpleNamespace(
            tokenPayDunya='paydunya-token',
            statutPaiement='en_attente',
            save=Mock(),
        )

        self.assertFalse(confirmer_facture(abonnement))

        self.assertEqual(abonnement.statutPaiement, 'en_attente')
        abonnement.save.assert_not_called()

    @patch('collecteurs.views.appeler_paydunya')
    def test_duplicate_confirmation_does_not_extend_paid_subscription(self, paydunya):
        paydunya.return_value = {
            'response_code': '00',
            'status': 'completed',
        }
        abonnement = SimpleNamespace(
            tokenPayDunya='paydunya-token',
            statutPaiement='paye',
            save=Mock(),
        )

        self.assertTrue(confirmer_facture(abonnement))

        abonnement.save.assert_not_called()
