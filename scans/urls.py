from django.urls import path
from .views import ScanDechetCreateView, ScanDechetListView


urlpatterns = [
    path('scans/', ScanDechetCreateView.as_view(), name='scan-create'),
    path('scans/historique/', ScanDechetListView.as_view(), name='scan-historique'),
]