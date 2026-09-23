from django.urls import path
from .views import ScanDechetCreateView, ScanDechetListView, ScanDechetDetailView, ScanDechetAdminListView, DashboardStatistiquesView, ScanDechetAdminDetailView


urlpatterns = [
    path('scans/', ScanDechetCreateView.as_view(), name='scan-create'),
    path('scans/historique/', ScanDechetListView.as_view(), name='scan-historique'),
    # Récupère le résultat d'un scan précis.
    path('scans/<int:idScan>/', ScanDechetDetailView.as_view(),name='scan-detail'),
        # Tous les scans pour l'administration.
            # Détail admin placé avant le détail classique.
    path('scans/admin/<int:idScan>/', ScanDechetAdminDetailView.as_view(), name='scan-admin-detail'),
    path( 'scans/admin/', ScanDechetAdminListView.as_view(), name='scan-admin'),
        # API utilisée par le tableau de bord administrateur.
    path('dashboard/statistiques/', DashboardStatistiquesView.as_view(), name='dashboard-statistiques'),
]