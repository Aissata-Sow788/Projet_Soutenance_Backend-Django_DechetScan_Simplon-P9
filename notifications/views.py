from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from .models import Notification
from .serializers import NotificationSerializer

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