from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import ValidationError

from .models import PanierDechet


@transaction.atomic
def reserver_quantites_paniers(utilisateur, lignes):
    """Réserve en une transaction le stock demandé par l'utilisateur."""
    panier_ids = sorted(ligne['idPanier'].pk for ligne in lignes)
    # Un ordre stable réduit le risque de deadlock lorsque plusieurs opérations
    # réservent plusieurs paniers au même moment.
    paniers = {
        panier.pk: panier
        for panier in PanierDechet.objects.select_for_update()
        .filter(idUtilisateur=utilisateur, pk__in=panier_ids)
        .order_by('pk')
    }

    if len(paniers) != len(panier_ids):
        raise ValidationError({
            'details': 'Un ou plusieurs paniers sont inexistants ou ne vous appartiennent pas.'
        })

    # Vérifier toutes les lignes avant la première décrémentation évite une
    # réservation partielle si une catégorie est en rupture.
    for ligne in lignes:
        panier = paniers[ligne['idPanier'].pk]
        nombre_objets = ligne['nombreObjets']
        if nombre_objets <= 0:
            raise ValidationError({'details': 'Chaque sélection doit contenir au moins un objet.'})
        if panier.nombreDisponible < nombre_objets:
            raise ValidationError({
                'details': (
                    f'Stock insuffisant pour {panier.idTypeDechet.nom}. '
                    f'Disponible : {panier.nombreDisponible} objet(s).'
                )
            })

    for ligne in lignes:
        panier = paniers[ligne['idPanier'].pk]
        PanierDechet.objects.filter(pk=panier.pk).update(
            nombreDisponible=F('nombreDisponible') - ligne['nombreObjets']
        )
    return paniers


@transaction.atomic
def restituer_quantites_paniers(lignes):
    """Restitue les objets retenus, sauf pour les anciennes lignes sans compteur."""
    for ligne in lignes.select_related('idPanier').order_by('idPanier_id'):
        # Les anciennes opérations ne connaissent que leur poids, pas le nombre
        # d'objets engagé ; leur attribuer un compte serait une conversion fictive.
        if ligne.nombreObjets is None:
            continue
        PanierDechet.objects.filter(pk=ligne.idPanier_id).update(
            nombreDisponible=F('nombreDisponible') + ligne.nombreObjets
        )
