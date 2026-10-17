import json
import hashlib
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from scans.models import ScanDechet

from notifications.models import Notification, PushSubscription

logger = logging.getLogger(__name__)


def creer_notification_apres_scan(
    scan: ScanDechet,
    message: str,
) -> Notification | None:
    """Enregistre le remerciement d'un scan lorsqu'un compte est connecté."""
    # Un scan anonyme n'a aucun compte auquel rattacher une notification.
    if scan.idUtilisateur_id is None:
        return None

    # La notification est conservée en base et apparaîtra dans l'API Angular.
    return Notification.objects.create(
        idUtilisateur=scan.idUtilisateur,
        titre='Merci pour votre scan !',
        message=message,
        lu=False,
    )


def _envoyer_push(notification: Notification) -> None:
    if not settings.WEBPUSH_VAPID_PUBLIC_KEY or not settings.WEBPUSH_VAPID_PRIVATE_KEY:
        return

    from pywebpush import WebPushException, webpush

    payload = json.dumps({
        'title': notification.titre,
        'body': notification.message,
        'url': '/notification',
        'notificationId': notification.idNotification,
    })
    subscriptions = PushSubscription.objects.filter(
        idUtilisateur=notification.idUtilisateur,
    )
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': subscription.endpoint,
                    'keys': {
                        'p256dh': subscription.p256dh,
                        'auth': subscription.auth,
                    },
                },
                data=payload,
                vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                vapid_claims={
                    'sub': f'mailto:{settings.WEBPUSH_VAPID_CLAIM_EMAIL}',
                },
            )
        except WebPushException as error:
            response = getattr(error, 'response', None)
            if response is not None and response.status_code in (404, 410):
                subscription.delete()
                continue
            logger.exception(
                'Push delivery failed for subscription %s',
                subscription.pk,
            )


def creer_notification(
    utilisateur,
    titre: str,
    message: str,
    *,
    sujet_email: str | None = None,
    corps_email: str | None = None,
) -> Notification:
    notification = Notification.objects.create(
        idUtilisateur=utilisateur,
        titre=titre,
        message=message,
        lu=False,
    )
    if sujet_email and corps_email and utilisateur.email:
        try:
            send_mail(
                sujet_email,
                corps_email,
                settings.DEFAULT_FROM_EMAIL,
                [utilisateur.email],
                fail_silently=False,
            )
        except Exception:
            logger.exception(
                'Email notification delivery failed for user %s',
                utilisateur.pk,
            )

    try:
        _envoyer_push(notification)
    except Exception:
        logger.exception(
            'Push notification delivery failed for notification %s',
            notification.pk,
        )
    return notification


def notifier_collecteur_nouvelle_demande(demande) -> None:
    from collecteurs.models import Collecteur

    collecteurs = Collecteur.objects.select_related('idUtilisateur').filter(
        statutValidation='valide',
        idUtilisateur__is_active=True,
    ).exclude(idUtilisateur=demande.idUtilisateur)
    for collecteur in collecteurs:
        creer_notification(
            collecteur.idUtilisateur,
            'Nouvelle demande de collecte',
            'Une nouvelle demande de collecte est disponible. Consultez les détails et décidez si vous souhaitez l’accepter.',
            sujet_email='Nouvelle demande de collecte disponible',
            corps_email=(
                'Bonjour,\n\n'
                'Une nouvelle demande de collecte est disponible sur DechetScan.\n\n'
                'Nous vous invitons à consulter votre espace collecteur pour découvrir les informations de la demande, notamment les déchets concernés, la localisation et les détails nécessaires à la collecte.\n\n'
                'Si cette demande correspond à votre zone d’intervention, vous pouvez consulter les options disponibles pour la prendre en charge.\n\n'
                'Merci de contribuer à une meilleure gestion des déchets.\n\n'
                'L’équipe DechetScan'
            ),
        )


def notifier_citoyen_statut_demande(demande, statut: str) -> None:
    utilisateur = demande.idUtilisateur
    if utilisateur is None:
        return

    messages = {
        'acceptee': (
            'Demande de collecte acceptée',
            'Bonne nouvelle ! Votre demande de collecte a été acceptée par le collecteur.',
            'Acceptée',
        ),
        'refus_individuel': (
            'Demande de collecte refusée par un collecteur',
            'Un collecteur a refusé votre demande. Elle reste disponible pour les autres collecteurs.',
            'Refusée par un collecteur (demande toujours disponible)',
        ),
        'refusee': (
            'Demande de collecte refusée',
            'Votre demande de collecte a été refusée.',
            'Refusée',
        ),
        'planifiee': (
            'Demande de collecte planifiée',
            'Votre demande de collecte a été planifiée.',
            'Planifiée',
        ),
    }
    contenu = messages.get(statut)
    if contenu is None:
        return
    titre, message, libelle_statut = contenu
    creer_notification(
        utilisateur,
        titre,
        message,
        sujet_email='Mise à jour de votre demande de collecte',
        corps_email=(
            'Bonjour,\n\n'
            'Nous vous informons que le statut de votre demande de collecte a été mis à jour.\n\n'
            f'Nouveau statut : {libelle_statut}\n\n'
            'Nous vous invitons à consulter votre espace DechetScan pour retrouver les détails de votre demande et les prochaines étapes.\n\n'
            'Merci d’utiliser DechetScan et de contribuer à un environnement plus propre.\n\n'
            'L’équipe DechetScan'
        ),
    )


def notifier_candidat_collecteur(collecteur, statut: str) -> None:
    utilisateur = collecteur.idUtilisateur
    messages = {
        'en_attente': (
            'Demande pour devenir collecteur reçue',
            'Votre demande pour devenir collecteur est en attente de validation par un administrateur.',
        ),
        'valide': (
            'Demande de collecteur acceptée',
            'Félicitations ! Votre demande pour devenir collecteur sur DechetScan a été acceptée. Vous pouvez désormais accéder à votre espace collecteur.',
        ),
        'rejete': (
            'Demande de collecteur refusée',
            'Votre demande pour devenir collecteur sur DechetScan a été refusée.',
        ),
    }
    contenu = messages.get(statut)
    if contenu is None:
        return
    titre, message = contenu
    if statut == 'valide':
        corps = (
            'Bonjour,\n\n'
            'Nous avons le plaisir de vous informer que votre demande pour devenir collecteur sur DechetScan a été acceptée.\n\n'
            'Vous pouvez désormais accéder à votre espace collecteur pour consulter les demandes de collecte et gérer vos interventions.\n\n'
            'Merci de rejoindre DechetScan et de participer à notre initiative pour une meilleure gestion des déchets.\n\n'
        )
    elif statut == 'rejete':
        corps = (
            'Bonjour,\n\n'
            'Nous vous informons que votre demande pour devenir collecteur sur DechetScan a été refusée.\n\n'
            'Vous pouvez consulter votre espace DechetScan pour retrouver les informations concernant votre candidature.\n\n'
        )
    else:
        corps = (
            'Bonjour,\n\n'
            'Nous confirmons la réception de votre demande pour devenir collecteur sur DechetScan.\n\n'
            'Votre dossier est en attente de traitement. Vous recevrez une nouvelle notification dès que l’administrateur aura pris une décision.\n\n'
        )
    corps += 'Cordialement,\nL’équipe DechetScan'
    creer_notification(
        utilisateur,
        titre,
        message,
        sujet_email='Mise à jour de votre demande pour devenir collecteur',
        corps_email=corps,
    )


@transaction.atomic
def enregistrer_abonnement_push(utilisateur, donnees: dict) -> PushSubscription:
    endpoint = donnees['endpoint']
    endpoint_hash = hashlib.sha256(endpoint.encode('utf-8')).hexdigest()
    abonnement, _ = PushSubscription.objects.update_or_create(
        endpoint_hash=endpoint_hash,
        defaults={
            'idUtilisateur': utilisateur,
            'endpoint': endpoint,
            'p256dh': donnees['p256dh'],
            'auth': donnees['auth'],
        },
    )
    return abonnement
