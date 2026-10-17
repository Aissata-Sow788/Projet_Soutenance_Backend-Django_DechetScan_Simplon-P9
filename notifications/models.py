import hashlib

from django.conf import settings
from django.db import models


class Notification(models.Model):
    # Identifiant unique de la notification.
    idNotification = models.AutoField(primary_key=True)

    # Utilisateur qui reçoit la notification.
    idUtilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    # Titre affiché dans la notification.
    titre = models.CharField(max_length=255)

    # Contenu de la notification.
    message = models.TextField()

    # Date et heure auxquelles la notification est créée/envoyée.
    dateEnvoi = models.DateTimeField(auto_now_add=True)

    # Indique si l'utilisateur a déjà lu la notification.
    lu = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.titre} - {self.idUtilisateur}"


class PushSubscription(models.Model):
    idPushSubscription = models.AutoField(primary_key=True)
    idUtilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.URLField(max_length=2048)
    endpoint_hash = models.CharField(max_length=64, unique=True, editable=False)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    dateCreation = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.endpoint_hash = hashlib.sha256(
            self.endpoint.encode('utf-8')
        ).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Push subscription for {self.idUtilisateur_id}"