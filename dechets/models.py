from django.conf import settings
from django.db import models
from django.utils import timezone


class TypeDechet(models.Model):
    idTypeDechet = models.AutoField(primary_key=True)
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.nom


class PanierDechet(models.Model):
    """Nombre d'objets d'une catégorie conservés par un citoyen."""

    idPanier = models.AutoField(primary_key=True)
    idUtilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='paniersDechets',
    )
    idTypeDechet = models.ForeignKey(
        TypeDechet,
        on_delete=models.PROTECT,
        related_name='paniers',
    )
    # Les anciennes valeurs en kilogrammes restent archivées, sans être
    # réinterprétées comme un nombre d'objets lors de la migration.
    quantiteHistoriqueKg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
    )
    nombreDisponible = models.PositiveIntegerField(default=0)
    unite = models.CharField(max_length=20, default='objet')
    dateMiseAJour = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['idUtilisateur', 'idTypeDechet'],
                name='unique_panier_citoyen_type_dechet',
            ),
            models.CheckConstraint(
                condition=models.Q(nombreDisponible__gte=0),
                name='panier_nombre_non_negative',
            ),
        ]

    def __str__(self):
        return f"{self.idUtilisateur} - {self.idTypeDechet} ({self.nombreDisponible} objets)"


class ConseilTri(models.Model):
    idConseil = models.AutoField(primary_key=True)
    consigne = models.TextField()

    idTypeDechet = models.OneToOneField(
        TypeDechet,
        on_delete=models.CASCADE,
        related_name='conseil'
    )

    def __str__(self):
        return self.consigne


class PrixDechet(models.Model):
    """
    Représente le tarif d'achat d'un type de déchet par les collecteurs.
    Un même type de déchet peut avoir plusieurs prix dans le temps
    (historique tarifaire via dateDebut / dateFin).
    Le champ 'actif' a été supprimé car il est redondant :
    on le calcule dynamiquement via la propriété 'est_actif'.
    """

    idPrix = models.AutoField(primary_key=True)

    # Type de déchet auquel ce tarif s'applique.
    # Un type de déchet peut avoir plusieurs tarifs dans le temps.
    idTypeDechet = models.ForeignKey(
        TypeDechet,
        on_delete=models.CASCADE,
        related_name='prix'
    )

    # NULL conserve les anciens tarifs généraux gérés par l'administration.
    idCollecteur = models.ForeignKey(
        'collecteurs.Collecteur',
        on_delete=models.CASCADE,
        related_name='tarifs',
        null=True,
        blank=True,
    )

    # Prix d'achat en FCFA par kilogramme.
    prixParKg = models.FloatField()

    # Commission prélevée par la plateforme sur chaque vente (en %).
    commission = models.FloatField()

    # Date à partir de laquelle ce tarif est applicable.
    dateDebut = models.DateField()

    # Date de fin du tarif. NULL signifie que le tarif est encore en vigueur.
    dateFin = models.DateField(null=True, blank=True)

    @property
    def est_actif(self):
        """
        Calcule dynamiquement si ce tarif est en vigueur aujourd'hui.
        Un tarif est actif si :
        - dateDebut <= aujourd'hui
        - ET dateFin est NULL (pas encore terminé) OU dateFin >= aujourd'hui
        """
        aujourd_hui = timezone.now().date()
        debut_ok = self.dateDebut <= aujourd_hui
        fin_ok = self.dateFin is None or self.dateFin >= aujourd_hui
        return debut_ok and fin_ok

    def __str__(self):
        return f"Prix {self.idTypeDechet.nom} - {self.prixParKg} FCFA/kg"