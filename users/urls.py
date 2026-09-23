from rest_framework.routers import DefaultRouter
from .views import InscriptionViewSet, ConnexionViewSet, UtilisateurConnecteView, GestionUtilisateurViewSet
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView


# Création du routeur Django REST Framework.
# Il permet de générer automatiquement les URLs liées à notre ViewSet.
router = DefaultRouter()


# On associe l'URL "register" à notre ViewSet d'inscription.
router.register(r'register', InscriptionViewSet, basename='register')
router.register(r'utilisateurs', GestionUtilisateurViewSet, basename='utilisateurs')

urlpatterns = [
    # Connexion JWT.
    path('login/', ConnexionViewSet.as_view(), name='login'),

    # Permet d'obtenir un nouvel access token
    # lorsque l'ancien a expiré.
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Informations de l'utilisateur connecté.
    path('me/', UtilisateurConnecteView.as_view(), name='me'),
]



# Récupération des URLs générées automatiquement par le routeur.
urlpatterns += router.urls