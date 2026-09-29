from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from dechets.models import ConseilTri, TypeDechet
from notifications.models import Notification
from notifications.services import creer_notification_apres_scan
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
