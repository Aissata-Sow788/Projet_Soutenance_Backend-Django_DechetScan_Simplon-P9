from django.urls import path

from .views import (
    NotificationListView,
    NotificationCreateView,
    NotificationReadView,
    PushConfigView,
    PushSubscriptionView,
)


urlpatterns = [
    # Récupérer les notifications de l'utilisateur connecté.
    path('', NotificationListView.as_view(), name='notification-list'),

    # Créer une nouvelle notification.
    path('create/', NotificationCreateView.as_view(), name='notification-create'),

    path('push/config/', PushConfigView.as_view(), name='push-config'),
    path('push/subscriptions/', PushSubscriptionView.as_view(), name='push-subscriptions'),

    # Marquer une notification précise comme lue.
    path('<int:pk>/read/', NotificationReadView.as_view(), name='notification-read'),

]