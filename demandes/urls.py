from rest_framework.routers import DefaultRouter
from .views import DemandeCollecteViewSet


router = DefaultRouter()

# Endpoints pour les demandes de collecte.
# GET/POST   /api/demandes/
# GET        /api/demandes/{id}/
# PATCH      /api/demandes/{id}/statut/
# DELETE     /api/demandes/{id}/
router.register(r'demandes', DemandeCollecteViewSet, basename='demande')

urlpatterns = router.urls
