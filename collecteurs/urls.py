from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    CollecteurViewSet,
    AbonnementCollecteurViewSet,
    AbonnementStatusView,
    ProfilCollecteurView,
    PayDunyaCallbackView,
    PayDunyaInvoiceView,
    PayDunyaPlansView,
    PayDunyaVerifyView,
)


router = DefaultRouter()

# Endpoints pour les collecteurs.
# GET/POST  /api/collecteurs/
# GET/PATCH /api/collecteurs/{id}/
# PATCH     /api/collecteurs/{id}/valider/
router.register(r'collecteurs', CollecteurViewSet, basename='collecteur')

# Endpoints pour les abonnements des collecteurs.
# GET/POST  /api/abonnements/
# GET       /api/abonnements/{id}/
router.register(r'abonnements', AbonnementCollecteurViewSet, basename='abonnement')

urlpatterns = [
    path(
        'collecteurs/mon-profil/',
        ProfilCollecteurView.as_view(),
        name='collecteur-mon-profil',
    ),
    path('abonnements/offres/', PayDunyaPlansView.as_view(), name='abonnement-offres'),
    path('abonnements/statut/', AbonnementStatusView.as_view(), name='abonnement-statut'),
    path('abonnements/initier-paiement/', PayDunyaInvoiceView.as_view(), name='abonnement-initier-paiement'),
    path('abonnements/verifier-paiement/', PayDunyaVerifyView.as_view(), name='abonnement-verifier-paiement'),
    path('paydunya/ipn/', PayDunyaCallbackView.as_view(), name='paydunya-ipn'),
] + router.urls
