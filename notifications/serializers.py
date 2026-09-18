from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    # Transforme les notifications Django en données JSON
    # utilisables par Angular et n8n.
    class Meta:
        model = Notification

        fields = ['idNotification', 'idUtilisateur', 'titre', 'message', 'dateEnvoi', 'lu',]

        # Ces champs sont gérés automatiquement par le serveur.
        # L'utilisateur ne doit donc pas pouvoir les modifier directement.
        read_only_fields = ['idNotification', 'idUtilisateur', 'dateEnvoi',]