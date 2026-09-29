from rest_framework.routers import DefaultRouter
from .views import PointCollecteViewSet, CollecteViewSet


router = DefaultRouter()

# Endpoints pour les points de collecte (existant).
router.register(r'points-collecte', PointCollecteViewSet, basename='point-collecte')

# Endpoints pour les opérations de collecte.
# GET/POST   /api/collectes/
# GET        /api/collectes/{id}/
# PATCH      /api/collectes/{id}/statut/
# DELETE     /api/collectes/{id}/
router.register(r'collectes', CollecteViewSet, basename='collecte')

urlpatterns = router.urls