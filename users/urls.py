from rest_framework.routers import DefaultRouter
from .views import InscriptionViewSet, ConnexionViewSet, UtilisateurConnecteView, GestionUtilisateurViewSet
from django.urls import path


# Création du routeur Django REST Framework.
# Il permet de générer automatiquement les URLs liées à notre ViewSet.
router = DefaultRouter()


# On associe l'URL "register" à notre ViewSet d'inscription.
router.register(r'register', InscriptionViewSet, basename='register')
router.register(r'utilisateurs', GestionUtilisateurViewSet, basename='utilisateurs')

  # Route de connexion JWT :
urlpatterns = [
    path('login/', ConnexionViewSet.as_view(), name='login'),
    path('me/', UtilisateurConnecteView.as_view(), name='me')
]



# Récupération des URLs générées automatiquement par le routeur.
urlpatterns += router.urls