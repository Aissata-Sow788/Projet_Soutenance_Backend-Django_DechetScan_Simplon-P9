from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.conf import settings
from .models import Notification
from .serializers import NotificationSerializer
from scans.models import ScanDechet
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model

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


class NotificationN8nCreateView(APIView):

    # Cette route utilise le secret n8n comme mécanisme de sécurité.
    # Elle ne nécessite donc pas de JWT utilisateur.
    permission_classes = [AllowAny]

    # Cette route est destinée à n8n.
    # Elle reçoit l'identifiant d'un scan et le message,
    # puis crée automatiquement une notification
    # pour l'utilisateur qui a effectué ce scan.

    def post(self, request):
        # Récupère le secret envoyé par n8n dans le header HTTP.
        secret = request.headers.get('X-N8N-SECRET')

        # Vérifie que le secret reçu correspond
        # au secret configuré dans Django.
        if secret != settings.N8N_SECRET:
            return Response(
                {
                    'detail': 'Accès non autorisé.'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Récupère les données envoyées par n8n.
        id_scan = request.data.get('idScan')
        message = request.data.get('message')

        # Vérifie que l'identifiant du scan et le message
        # ont bien été fournis.
        if not id_scan or not message:
            return Response(
                {
                    'detail': 'idScan et message sont obligatoires.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Recherche le scan correspondant.
        try:
            scan = ScanDechet.objects.select_related('idUtilisateur').get(idScan=id_scan)

        except ScanDechet.DoesNotExist:
            return Response({ 'detail': 'Scan introuvable.' }, status=status.HTTP_404_NOT_FOUND)

        # Vérifie que le scan est associé à un utilisateur.
        if scan.idUtilisateur is None:
            return Response({ 'detail': 'Ce scan n’est associé à aucun utilisateur.' },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crée la notification pour l'utilisateur
        # qui a réalisé le scan.
        notification = Notification.objects.create(
            idUtilisateur=scan.idUtilisateur,
            titre='Merci pour votre scan !',
            message=message,
            lu=False
        )

        # Retourne la notification créée.
        return Response(NotificationSerializer(notification).data,
            status=status.HTTP_201_CREATED
        )

class NotificationDailyN8nCreateView(APIView):

    # Cette route est appelée uniquement par n8n.
    # Elle n'utilise donc pas le JWT de l'utilisateur.
    permission_classes = [AllowAny]

    def post(self, request):

        # Vérifie le secret envoyé par n8n.
        secret = request.headers.get('X-N8N-SECRET')

        if secret != settings.N8N_SECRET:
            return Response(
                {'detail': 'Accès non autorisé.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Récupère tous les utilisateurs enregistrés.
        User = get_user_model()
        utilisateurs = User.objects.all()

        # Conseil affiché chaque jour.
        message = (
            "Pensez à bien rincer vos emballages avant de les trier. "
            "Cela évite d'altérer la chaîne de valorisation locale."
        )

        # Crée une notification pour chaque utilisateur.
        notifications_creees = []

        for utilisateur in utilisateurs:

            notification = Notification.objects.create(
                idUtilisateur=utilisateur,
                titre='Conseil du jour',
                message=message,
                lu=False
            )

            notifications_creees.append(notification)

        return Response(
            {
                'message': 'Conseil quotidien envoyé.',
                'nombre': len(notifications_creees)
            },
            status=status.HTTP_201_CREATED
        )