from django.urls import path
from .views import ScanDechetCreateView, ScanDechetListView


urlpatterns = [
    path('', ScanDechetCreateView.as_view(), name='scan-create'),
    path('historique/', ScanDechetListView.as_view(), name='scan-historique'),
]