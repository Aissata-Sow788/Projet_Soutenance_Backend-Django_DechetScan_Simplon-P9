from django.db import models
from django.conf import settings


class DemandeCollecte(models.Model):
    """
    Représente une demande de collecte de déchets soumise par un citoyen.
    Les catégories et quantités sont conservées dans DetailDemandeCollecte.
    La demande passe par différents statuts jusqu'à sa résolution.
    """

    # Choix possibles pour le type de demande.
    TYPE_DEMANDE_CHOICES = [
        ('ramassage', 'Ramassage à domicile'),
        ('depot', 'Dépôt en point de collecte'),
    ]

    # Choix possibles pour le statut de la demande.
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('acceptee', 'Acceptée'),
        ('refusee', 'Refusée'),
        ('planifiee', 'Planifiée'),
        ('en_cours', 'En cours'),
        ('terminee', 'Terminée'),
        ('annulee', 'Annulée'),
    ]

    idDemande = models.AutoField(primary_key=True)

    # Citoyen qui soumet la demande.
    # Si l'utilisateur est supprimé, la demande reste (SET_NULL).
    idUtilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='demandes'
    )

    # Type de demande : ramassage à domicile ou dépôt en point de collecte.
    typeDemande = models.CharField(
        max_length=20,
        choices=TYPE_DEMANDE_CHOICES,
        default='ramassage'
    )

    # Prix proposé par le citoyen pour la collecte (en FCFA).
    # Peut être NULL si le citoyen laisse le collecteur fixer le prix.
    prixPropose = models.FloatField(null=True, blank=True)

    # Quartier où se trouve le citoyen (ex: "Médina", "Plateau", "Pikine").
    # Remplace le champ 'adresse' supprimé, plus précis pour la localisation locale.
    quartier = models.CharField(max_length=100, blank=True)

    # Coordonnées GPS récupérées automatiquement par le navigateur (géolocalisation).
    # Optionnelles : si l'utilisateur refuse la géolocalisation,
    # la demande peut quand même être soumise avec uniquement le quartier.
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Date à laquelle la demande a été soumise (générée automatiquement).
    dateDemande = models.DateTimeField(auto_now_add=True)

    # Date souhaitée par le citoyen pour la collecte.
    dateSouhaitee = models.DateTimeField(null=True, blank=True)

    # Statut actuel de la demande.
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='en_attente'
    )
    # Empêche de restituer deux fois un stock rendu lors d'une annulation.
    stockRestitue = models.BooleanField(default=False)

    # Collecteur qui a accepté et pris en charge cette demande.
    # NULL tant qu'aucun collecteur n'a accepté (statut en_attente).
    # SET_NULL pour conserver l'historique si le collecteur est supprimé.
    collecteurAttribue = models.ForeignKey(
        'collecteurs.Collecteur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='demandesAttribuees'
    )

    # Les refus sont propres à chaque collecteur ; la demande reste disponible
    # aux autres tant qu'elle n'a pas été acceptée.
    refuseurs = models.ManyToManyField(
        'collecteurs.Collecteur',
        blank=True,
        related_name='demandesRefusees'
    )

    def __str__(self):
        return f"Demande #{self.idDemande} - {self.idUtilisateur} ({self.statut})"


class DetailDemandeCollecte(models.Model):
    """Objets sélectionnés et poids pesé pour une catégorie de demande."""

    idDetail = models.AutoField(primary_key=True)
    idDemande = models.ForeignKey(
        DemandeCollecte,
        on_delete=models.CASCADE,
        related_name='details',
    )
    idPanier = models.ForeignKey(
        'dechets.PanierDechet',
        on_delete=models.PROTECT,
        related_name='detailsDemandes',
    )
    poidsKg = models.DecimalField(max_digits=12, decimal_places=3)
    # NULL distingue les anciennes demandes dont le nombre d'objets est inconnu.
    nombreObjets = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['idDemande', 'idPanier'],
                name='unique_panier_par_demande',
            ),
            models.CheckConstraint(
                condition=models.Q(poidsKg__gt=0),
                name='detail_demande_poids_positif',
            ),
            models.CheckConstraint(
                condition=models.Q(nombreObjets__isnull=True) | models.Q(nombreObjets__gt=0),
                name='detail_demande_objets_positif',
            ),
        ]
