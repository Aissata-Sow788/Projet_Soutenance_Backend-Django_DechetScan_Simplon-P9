from rest_framework.routers import DefaultRouter
from .views import PointCollecteViewSet


router = DefaultRouter()

router.register(r'points-collecte', PointCollecteViewSet, basename='point-collecte')

urlpatterns = router.urls