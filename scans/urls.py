from django.urls import path
from .views import (
    ScanDechetCreateView,
    ScanDechetListView,
    ScanDechetDetailView,
    ScanDechetAdminListView,
    DashboardStatistiquesView,
    ScanDechetAdminDetailView,
    StatsAccueilPublicView,
)


urlpatterns = [
    path('scans/', ScanDechetCreateView.as_view(), name='scan-create'),
    path('scans/historique/', ScanDechetListView.as_view(), name='scan-historique'),
    path('scans/<int:idScan>/', ScanDechetDetailView.as_view(), name='scan-detail'),
    path('scans/admin/<int:idScan>/', ScanDechetAdminDetailView.as_view(), name='scan-admin-detail'),
    path('scans/admin/', ScanDechetAdminListView.as_view(), name='scan-admin'),
    path('dashboard/statistiques/', DashboardStatistiquesView.as_view(), name='dashboard-statistiques'),
    # Endpoint public pour les statistiques de la page d'accueil.
    # Accessible sans token JWT — données inoffensives.
    path('stats/accueil/', StatsAccueilPublicView.as_view(), name='stats-accueil-public'),
]