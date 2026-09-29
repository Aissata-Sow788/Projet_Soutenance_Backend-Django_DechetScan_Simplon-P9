from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dechets.models import ConseilTri
from notifications.models import Notification


class Command(BaseCommand):
    """Crée les notifications du jour pour les utilisateurs actifs.

    À lancer une fois par jour avec le planificateur du serveur, par exemple cron.
    """

    help = 'Envoie un conseil de tri quotidien à chaque utilisateur actif.'

    def handle(self, *args, **options):
        # La date locale de Django détermine le conseil et la journée anti-doublon.
        jour = timezone.localdate()

        # Les conseils du référentiel servent de contenu éditable par l'administration.
        conseils = list(
            ConseilTri.objects.select_related('idTypeDechet').order_by('idConseil')
        )
        if not conseils:
            raise CommandError(
                'Aucun conseil de tri disponible dans le référentiel des déchets.'
            )

        # Le conseil change chaque jour en suivant l'ordre du référentiel.
        conseil = conseils[jour.toordinal() % len(conseils)]
        message = f'{conseil.idTypeDechet.nom} : {conseil.consigne}'

        # Une exécution répétée le même jour ne doit pas créer de doublons.
        titre = 'Conseil du jour'
        deja_notifies = Notification.objects.filter(
            titre=titre,
            dateEnvoi__date=jour,
        ).values_list('idUtilisateur_id', flat=True)
        deja_notifies_ids = set(deja_notifies)

        # Les comptes désactivés ne reçoivent pas de nouveaux conseils.
        utilisateur = get_user_model()
        utilisateurs_a_notifier = utilisateur.objects.filter(
            is_active=True
        ).exclude(pk__in=deja_notifies_ids)

        # Prépare toutes les notifications puis les insère efficacement en une requête.
        notifications = [
            Notification(
                idUtilisateur=destinataire,
                titre=titre,
                message=message,
                lu=False,
            )
            for destinataire in utilisateurs_a_notifier
        ]
        Notification.objects.bulk_create(notifications)

        # Le résumé permet au planificateur et aux journaux du serveur de confirmer l'envoi.
        self.stdout.write(
            self.style.SUCCESS(
                f'Conseil quotidien créé pour {len(notifications)} utilisateur(s).'
            )
        )
