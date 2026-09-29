from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    VenteDechetViewSet,
    VentePaiementInitierView,
    VentePaiementVerifierView,
    VentePaiementCallbackView,
)


router = DefaultRouter()

# Endpoints CRUD ventes.
# GET/POST   /api/ventes/
# GET        /api/ventes/{id}/
# PATCH      /api/ventes/{id}/statut/
# DELETE     /api/ventes/{id}/
router.register(r'ventes', VenteDechetViewSet, basename='vente')

urlpatterns = [

    # ── Paiement citoyen via PayDunya ──────────────────────────
    # Le collecteur initie un paiement pour régler le citoyen vendeur.
    path(
        'ventes/paiement/initier/',
        VentePaiementInitierView.as_view(),
        name='vente-paiement-initier'
    ),

    # Vérification du statut du paiement (polling Angular).
    # GET /api/ventes/paiement/verifier/?reference=VP-xxx
    path(
        'ventes/paiement/verifier/',
        VentePaiementVerifierView.as_view(),
        name='vente-paiement-verifier'
    ),

    # Callback IPN PayDunya — appelé directement par PayDunya.
    # POST /api/ventes/paiement/ipn/
    path(
        'ventes/paiement/ipn/',
        VentePaiementCallbackView.as_view(),
        name='vente-paiement-ipn'
    ),

] + router.urls
