from django.db import models
from django.conf import settings


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