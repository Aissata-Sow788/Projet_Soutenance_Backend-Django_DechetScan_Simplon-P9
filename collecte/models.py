from django.db import models
from django.conf import settings
from dechets.models import TypeDechet


class PointCollecte(models.Model):
    STATUT_CHOICES = [
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
    ]

    idPoint = models.AutoField(primary_key=True)
    nom = models.CharField(max_length=150)
    ville = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='actif')
    heureOuverture = models.CharField(max_length=5)  # format "HH:MM"
    heureFermeture = models.CharField(max_length=5)

    # Relation many-to-many : un point accepte plusieurs types, un type est accepté par plusieurs points
    dechetsAcceptes = models.ManyToManyField(TypeDechet, related_name='pointsCollecte')

    # Admin qui gère ce point (relation "gère" 1 Utilisateur -> 0..* PointCollecte)
    gerePar = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='pointsGeres'
    )

    def __str__(self):
        return self.nom


class Collecte(models.Model):
    """
    Représente une opération de collecte de déchets réalisée par un collecteur.
    Elle peut être planifiée à l'avance ou réalisée directement.

    Relations depuis le diagramme :
    - Collecteur "realise" une Collecte (idCollecteur FK, obligatoire)
    - Collecte "concerne" un PointCollecte (idPoint FK, optionnel 0..1)
    - Collecte "est basé sur" une DemandeCollecte (idDemande FK, optionnel 0..1)
    - PointCollecte "accepte" des Collectes (déjà couvert par idPoint FK ci-dessus)
    """

    # Choix possibles pour le statut d'une collecte.
    # Correspond exactement à l'énumération StatutCollecte du diagramme.
    STATUT_CHOICES = [
        ('planifiee', 'Planifiée'),
        ('en_cours', 'En cours'),
        ('terminee', 'Terminée'),
        ('annulee', 'Annulée'),
    ]

    idCollecte = models.AutoField(primary_key=True)

    # Collecteur professionnel qui réalise cette collecte.
    # SET_NULL pour conserver l'historique si le collecteur est supprimé.
    idCollecteur = models.ForeignKey(
        'collecteurs.Collecteur',
        on_delete=models.SET_NULL,
        null=True,
        related_name='collectes'
    )

    # Point de collecte concerné par cette opération (optionnel).
    # NULL si la collecte se fait directement chez le citoyen (ramassage à domicile).
    idPoint = models.ForeignKey(
        PointCollecte,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collectes'
    )

    # Demande de collecte à l'origine de cette opération (optionnel).
    # NULL si la collecte n'est pas liée à une demande spécifique.
    idDemande = models.ForeignKey(
        'demandes.DemandeCollecte',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collectes'
    )

    # Date et heure prévues pour la collecte.
    datePlanifiee = models.DateTimeField()

    # Statut actuel de la collecte.
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='planifiee'
    )

    # Date et heure réelles de réalisation de la collecte.
    # NULL tant que la collecte n'est pas terminée.
    dateRealisation = models.DateTimeField(null=True, blank=True)

    # Quantité totale de déchets récupérés en kilogrammes.
    # NULL tant que la collecte n'est pas terminée.
    quantiteRecuperee = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Collecte #{self.idCollecte} - {self.statut} ({self.datePlanifiee.date()})"