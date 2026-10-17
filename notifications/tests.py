from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from collecteurs.models import Collecteur
from dechets.models import ConseilTri, TypeDechet
from demandes.models import DemandeCollecte
from notifications.models import Notification, PushSubscription
from notifications.services import (
    creer_notification_apres_scan,
    notifier_citoyen_statut_demande,
    notifier_collecteur_nouvelle_demande,
    notifier_candidat_collecteur,
)
from scans.models import ScanDechet


class NotificationApresScanTests(TestCase):
    """Vérifie la création du remerciement depuis le traitement Django du scan."""

    def test_cree_notification_pour_un_utilisateur_connecte(self):
        utilisateur = get_user_model().objects.create_user(
            email='citoyen@example.com',
            password='mot-de-passe-test',
        )
        scan = ScanDechet(idUtilisateur=utilisateur)

        notification = creer_notification_apres_scan(scan, 'Merci pour votre scan !')

        self.assertIsNotNone(notification)
        self.assertEqual(notification.idUtilisateur, utilisateur)
        self.assertEqual(notification.titre, 'Merci pour votre scan !')
        self.assertFalse(notification.lu)

    def test_ne_cree_pas_de_notification_pour_un_scan_anonyme(self):
        scan = ScanDechet(idUtilisateur=None)

        notification = creer_notification_apres_scan(scan, 'Merci pour votre scan !')

        self.assertIsNone(notification)
        self.assertEqual(Notification.objects.count(), 0)


class ConseilQuotidienCommandTests(TestCase):
    """Vérifie l'envoi quotidien et son comportement idempotent."""

    def setUp(self):
        self.utilisateur = get_user_model().objects.create_user(
            email='citoyen@example.com',
            password='mot-de-passe-test',
        )
        type_dechet = TypeDechet.objects.create(nom='Plastique')
        ConseilTri.objects.create(
            idTypeDechet=type_dechet,
            consigne='Rincez les emballages avant de les trier.',
        )

    def test_cree_un_conseil_et_ne_le_duplique_pas_dans_la_journee(self):
        sortie = StringIO()

        call_command('envoyer_conseil_quotidien', stdout=sortie)
        call_command('envoyer_conseil_quotidien', stdout=sortie)

        self.assertEqual(Notification.objects.count(), 1)
        notification = Notification.objects.get()
        self.assertEqual(notification.idUtilisateur, self.utilisateur)
        self.assertEqual(notification.titre, 'Conseil du jour')
        conseils_disponibles = {
            f'{conseil.idTypeDechet.nom} : {conseil.consigne}'
            for conseil in ConseilTri.objects.select_related('idTypeDechet')
        }
        self.assertIn(notification.message, conseils_disponibles)

    def test_echoue_clairement_si_aucun_conseil_n_est_configure(self):
        ConseilTri.objects.all().delete()

        with self.assertRaises(CommandError):
            call_command('envoyer_conseil_quotidien')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NotificationsMetierTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.citoyen = user_model.objects.create_user(
            email='citoyen@example.com',
            password='mot-de-passe-test',
        )
        self.collecteur_user = user_model.objects.create_user(
            email='collecteur@example.com',
            password='mot-de-passe-test',
        )
        self.collecteur = Collecteur.objects.create(
            idUtilisateur=self.collecteur_user,
            statutValidation='valide',
        )
        self.demande = DemandeCollecte.objects.create(
            idUtilisateur=self.citoyen,
        )

    def test_notifie_le_collecteur_d_une_nouvelle_demande_par_app_et_email(self):
        notifier_collecteur_nouvelle_demande(self.demande)

        notification = Notification.objects.get(
            idUtilisateur=self.collecteur_user,
        )
        self.assertIn('nouvelle demande', notification.message.lower())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Nouvelle demande de collecte disponible')
        self.assertIn('les déchets concernés', mail.outbox[0].body)

    def test_notifie_le_citoyen_du_refus_individuel_sans_clore_sa_demande(self):
        notifier_citoyen_statut_demande(self.demande, 'refus_individuel')

        notification = Notification.objects.get(idUtilisateur=self.citoyen)
        self.assertIn('reste disponible', notification.message)
        self.assertIn('toujours disponible', mail.outbox[0].body)

    def test_notifie_le_citoyen_de_la_planification(self):
        notifier_citoyen_statut_demande(self.demande, 'planifiee')

        notification = Notification.objects.get(idUtilisateur=self.citoyen)
        self.assertEqual(notification.titre, 'Demande de collecte planifiée')
        self.assertIn('Nouveau statut : Planifiée', mail.outbox[0].body)

    def test_notifie_le_candidat_a_chaque_decision(self):
        notifier_candidat_collecteur(self.collecteur, 'valide')

        notification = Notification.objects.get(
            idUtilisateur=self.collecteur_user,
        )
        self.assertIn('Félicitations', notification.message)
        self.assertIn('désormais accéder', mail.outbox[0].body)

    def test_notifie_le_refus_de_candidature_sans_feliciter_le_candidat(self):
        notifier_candidat_collecteur(self.collecteur, 'rejete')

        self.assertIn(
            'refusée',
            Notification.objects.get(idUtilisateur=self.collecteur_user).message,
        )
        self.assertIn('a été refusée', mail.outbox[0].body)
        self.assertNotIn('plaisir', mail.outbox[0].body)

    @override_settings(
        WEBPUSH_VAPID_PUBLIC_KEY='public-key',
        WEBPUSH_VAPID_PRIVATE_KEY='private-key',
    )
    def test_enregistre_et_supprime_un_abonnement_push_du_compte(self):
        client = APIClient()
        client.force_authenticate(self.citoyen)
        payload = {
            'endpoint': 'https://fcm.googleapis.com/fcm/send/test-token',
            'p256dh': 'public-encryption-key',
            'auth': 'authentication-secret',
        }

        config = client.get('/api/notifications/push/config/')
        response = client.post(
            '/api/notifications/push/subscriptions/',
            payload,
            format='json',
        )

        self.assertEqual(config.status_code, 200)
        self.assertTrue(config.data['enabled'])
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            PushSubscription.objects.filter(
                idUtilisateur=self.citoyen,
                endpoint=payload['endpoint'],
            ).exists()
        )

        deleted = client.delete(
            '/api/notifications/push/subscriptions/',
            {'endpoint': payload['endpoint']},
            format='json',
        )

        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(PushSubscription.objects.exists())
