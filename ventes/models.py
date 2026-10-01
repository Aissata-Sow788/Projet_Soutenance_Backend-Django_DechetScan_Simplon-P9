from django.db import models
from django.conf import settings
from dechets.models import TypeDechet
from collecteurs.models import Collecteur


class VenteDechet(models.Model):
    """
    Représente une transaction de vente de déchets entre un citoyen
    et un collecteur professionnel.

    Relations confirmées depuis le diagramme :
    - Utilisateur "place" une vente (idUtilisateur FK)
    - Collecteur "Achete" une vente (idCollecteur FK)
    - VenteDechet "concerne" un TypeDechet (idTypeDechet FK)

    
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

    # Type de déchet vendu (plastique, métal, verre, etc.).
    # SET_NULL pour conserver l'historique si le type est supprimé.
    idTypeDechet = models.ForeignKey(
        TypeDechet,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ventes'
    )

    # Quantité de déchets vendus en kilogrammes.
    quantite = models.FloatField()

    # Prix total payé pour cette vente (en FCFA).
    prixPaye = models.FloatField()

    # Méthode de paiement utilisée (ex: "Wave", "Orange Money").
    methodePaiement = models.CharField(max_length=50, blank=True)

    # Statut actuel du paiement.
    statutPaiement = models.CharField(
        max_length=20,
        choices=STATUT_PAIEMENT_CHOICES,
        default='en_attente'
    )

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
        return f"Vente #{self.idVente} - {self.idTypeDechet} ({self.quantite} kg)"
