from scans.models import ScanDechet

from notifications.models import Notification


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
