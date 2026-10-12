from rest_framework.routers import DefaultRouter

from .views import (
    PanierDechetViewSet,
    TypeDechetViewSet,
    ConseilTriViewSet,
    PrixDechetViewSet,
)


router = DefaultRouter()

router.register(r'types', TypeDechetViewSet, basename='type-dechet')

router.register(r'conseils', ConseilTriViewSet, basename='conseil-tri')

# Endpoint pour les tarifs d'achat des déchets.
router.register(r'prix-dechets', PrixDechetViewSet, basename='prix-dechet')
# Les citoyens consultent et alimentent leurs propres paniers.
router.register(r'paniers', PanierDechetViewSet, basename='panier-dechet')

urlpatterns = router.urls