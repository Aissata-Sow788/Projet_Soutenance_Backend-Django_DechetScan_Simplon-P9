from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.conf import settings
from .models import Notification, PushSubscription
from .serializers import NotificationSerializer, PushSubscriptionSerializer
from .services import enregistrer_abonnement_push

class NotificationListView(APIView):
    # Seuls les utilisateurs connectés peuvent consulter leurs notifications.
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Récupère uniquement les notifications de l'utilisateur connecté.
        notifications = Notification.objects.filter(
            idUtilisateur=request.user
        ).order_by('-dateEnvoi')

        # Transforme les notifications Django en JSON.
        serializer = NotificationSerializer(notifications, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

class NotificationCreateView(APIView):
    # Cette route permet de créer une notification
    # pour l'utilisateur actuellement connecté.
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=NotificationSerializer,
        responses=NotificationSerializer
    )
    def post(self, request):
        # Vérifie les données envoyées dans la requête.
        serializer = NotificationSerializer(data=request.data)

        if serializer.is_valid():
            # Associe automatiquement la notification
            # à l'utilisateur actuellement connecté.
            notification = serializer.save(
                idUtilisateur=request.user
            )

            # Retourne la notification créée.
            return Response(
                NotificationSerializer(notification).data,
                status=status.HTTP_201_CREATED
            )

        # Retourne les erreurs si les données sont invalides.
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

class NotificationReadView(APIView):
    # Seuls les utilisateurs connectés peuvent modifier leurs notifications.
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        # Recherche uniquement une notification appartenant à l'utilisateur connecté.
        try:
            notification = Notification.objects.get(
                idNotification=pk,
                idUtilisateur=request.user
            )
        except Notification.DoesNotExist:
            return Response(
                {'detail': 'Notification introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Une notification ouverte devient lue.
        notification.lu = True
        notification.save(update_fields=['lu'])

        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_200_OK
        )


class PushConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        public_key = settings.WEBPUSH_VAPID_PUBLIC_KEY
        return Response({
            'enabled': bool(
                public_key and settings.WEBPUSH_VAPID_PRIVATE_KEY
            ),
            'publicKey': public_key or None,
        })


class PushSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        abonnement = enregistrer_abonnement_push(
            request.user,
            serializer.validated_data,
        )
        return Response(
            {'id': abonnement.pk},
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        endpoint = request.data.get('endpoint')
        if not endpoint:
            return Response(
                {'detail': 'Le endpoint de l’abonnement est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        PushSubscription.objects.filter(
            idUtilisateur=request.user,
            endpoint=endpoint,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)