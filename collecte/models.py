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