from rest_framework.routers import DefaultRouter

from .views import TypeDechetViewSet, ConseilTriViewSet


router = DefaultRouter()

router.register(r'types', TypeDechetViewSet, basename='type-dechet')

router.register(r'conseils', ConseilTriViewSet, basename='conseil-tri')

urlpatterns = router.urls