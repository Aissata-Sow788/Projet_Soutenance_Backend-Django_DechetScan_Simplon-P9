from rest_framework.routers import DefaultRouter

from .views import TypeDechetViewSet, ConseilTriViewSet, PrixDechetViewSet


router = DefaultRouter()

router.register(r'types', TypeDechetViewSet, basename='type-dechet')

router.register(r'conseils', ConseilTriViewSet, basename='conseil-tri')

# Endpoint pour les tarifs d'achat des déchets.
router.register(r'prix-dechets', PrixDechetViewSet, basename='prix-dechet')

urlpatterns = router.urls