from django.db import models
from django.conf import settings


class Notification(models.Model):
    idNotification = models.AutoField(primary_key=True)
    titre = models.CharField(max_length=150)
    message = models.TextField()
    dateEnvoi = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)

    idUtilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    def __str__(self):
        return self.titre