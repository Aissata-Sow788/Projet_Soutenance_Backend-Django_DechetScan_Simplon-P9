from django.urls import path

from .views import (NotificationListView, NotificationCreateView, NotificationReadView, NotificationN8nCreateView, NotificationDailyN8nCreateView)


urlpatterns = [
    # Récupérer les notifications de l'utilisateur connecté.
    path('', NotificationListView.as_view(), name='notification-list'),

    # Créer une nouvelle notification.
    path('create/', NotificationCreateView.as_view(), name='notification-create'),

    # Marquer une notification précise comme lue.
    path('<int:pk>/read/', NotificationReadView.as_view(), name='notification-read'),

        # Route utilisée par n8n pour créer une notification
    # à partir de l'identifiant d'un scan.
    path('internal/scan/', NotificationN8nCreateView.as_view(), name='notification-n8n-create'),

        # Route utilisée par n8n pour le conseil quotidien.
    path(
        'internal/daily/',
        NotificationDailyN8nCreateView.as_view(),
        name='notification-daily-n8n-create'
    ),
]