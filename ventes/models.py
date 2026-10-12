from django.db import models
from django.conf import settings
from collecteurs.models import Collecteur


class VenteDechet(models.Model):
    """
    Représente une transaction de vente de déchets entre un citoyen
    et un collecteur professionnel.

    Les déchets et quantités vendues sont conservés dans DetailVenteDechet.

    """

    # Choix possibles pour le statut du paiement.
    STATUT_PAIEMENT_CHOICES = [
        ('en_attente', 'En attente'),
        ('paye', 'Payé'),
        ('echoue', 'Échoué'),
        ('rembourse', 'Remboursé'),
    ]

    idVente = models.AutoField(primary_key=True)

    # Citoyen qui vend ses déchets.
    # SET_NULL pour conserver l'historique si l'utilisateur supprime son compte.
    idUtilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ventes'
    )

    # Collecteur professionnel qui achète les déchets.
    # SET_NULL pour conserver l'historique si le collecteur est supprimé.
    idCollecteur = models.ForeignKey(
        Collecteur,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ventes'
    )

    # Total figé depuis les détails pour conserver le montant convenu historique.
    prixPaye = models.DecimalField(max_digits=14, decimal_places=2)

    # Méthode de paiement utilisée (ex: "Wave", "Orange Money").
    methodePaiement = models.CharField(max_length=50, blank=True)

    # Statut actuel du paiement.
    statutPaiement = models.CharField(
        max_length=20,
        choices=STATUT_PAIEMENT_CHOICES,
        default='en_attente'
    )
    # Empêche de restituer deux fois le stock après suppression d'une vente.
    stockRestitue = models.BooleanField(default=False)

    # Référence unique de la transaction (numéro retourné par le système de paiement).
    referencePaiement = models.CharField(max_length=100, blank=True)

    # Token PayDunya de la facture créée pour payer le citoyen.
    # NULL tant qu'aucune facture PayDunya n'a été initiée pour cette vente.
    # Utilisé pour confirmer le paiement via l'API PayDunya.
    tokenPayDunya = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )

    # Date et heure à laquelle la vente a été enregistrée.
    dateVente = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Vente #{self.idVente} - {self.prixPaye} FCFA"


class DetailVenteDechet(models.Model):
    """Objets vendus, poids mesuré et tarif unitaire figé d'une ligne."""

    idDetail = models.AutoField(primary_key=True)
    idVente = models.ForeignKey(
        VenteDechet,
        on_delete=models.CASCADE,
        related_name='details',
    )
    idPanier = models.ForeignKey(
        'dechets.PanierDechet',
        on_delete=models.PROTECT,
        related_name='detailsVentes',
    )
    poidsKg = models.DecimalField(max_digits=12, decimal_places=3)
    # NULL distingue les ventes historiques dont le nombre d'objets est inconnu.
    nombreObjets = models.PositiveIntegerField(null=True, blank=True)
    prixParKg = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['idVente', 'idPanier'],
                name='unique_panier_par_vente',
            ),
            models.CheckConstraint(
                condition=models.Q(poidsKg__gt=0),
                name='detail_vente_poids_positif',
            ),
            models.CheckConstraint(
                condition=models.Q(nombreObjets__isnull=True) | models.Q(nombreObjets__gt=0),
                name='detail_vente_objets_positif',
            ),
            models.CheckConstraint(
                condition=models.Q(prixParKg__gte=0),
                name='detail_vente_prix_non_negative',
            ),
        ]

    @property
    def sousTotal(self):
        """Calcule le montant de ligne sans dupliquer cette valeur en base."""
        return self.poidsKg * self.prixParKg
