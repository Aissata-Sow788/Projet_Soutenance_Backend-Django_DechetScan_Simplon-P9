from urllib.parse import urlparse

from rest_framework import serializers
from .models import Notification, PushSubscription


class NotificationSerializer(serializers.ModelSerializer):
    # Transforme les notifications Django en données JSON
    # utilisables par l'interface Angular.
    class Meta:
        model = Notification

        fields = ['idNotification', 'idUtilisateur', 'titre', 'message', 'dateEnvoi', 'lu',]

        # Ces champs sont gérés automatiquement par le serveur.
        # L'utilisateur ne doit donc pas pouvoir les modifier directement.
        read_only_fields = ['idNotification', 'idUtilisateur', 'dateEnvoi',]


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = ['endpoint', 'p256dh', 'auth']

    def validate_endpoint(self, endpoint):
        parsed = urlparse(endpoint)
        hostname = (parsed.hostname or '').lower()
        allowed_domains = (
            'fcm.googleapis.com',
            'push.services.mozilla.com',
            'notify.windows.com',
            'web.push.apple.com',
        )
        if parsed.scheme != 'https' or not any(
            hostname == domain or hostname.endswith(f'.{domain}')
            for domain in allowed_domains
        ):
            raise serializers.ValidationError(
                'Une URL HTTPS d’un fournisseur de notifications reconnu est obligatoire.'
            )
        return endpoint