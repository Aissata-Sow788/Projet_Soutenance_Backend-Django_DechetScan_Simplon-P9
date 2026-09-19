from django.db import models
from django.conf import settings
from dechets.models import TypeDechet


class ScanDechet(models.Model):
    # Identifiant unique du scan.
    idScan = models.AutoField(primary_key=True)

    # Date et heure auxquelles le scan a été effectué.
    dateScan = models.DateTimeField(auto_now_add=True)

    # Photo envoyée par le citoyen.
    photoUrl = models.ImageField(upload_to='scans/')

    # Utilisateur ayant effectué le scan.
    # Peut être NULL si le scan est anonyme.
    idUtilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scans'
    )

    def __str__(self):
        return f"Scan #{self.idScan} - {self.dateScan.date()}"


class AnalyseIA(models.Model):
    idAnalyse = models.AutoField(primary_key=True)
    dateAnalyse = models.DateTimeField(auto_now_add=True)

    idScan = models.OneToOneField(
        ScanDechet,
        on_delete=models.CASCADE,
        related_name='analyseIA'
    )

    def __str__(self):
        return f"Analyse #{self.idAnalyse}"


class DetectionIA(models.Model):
    # Identifiant unique de la détection.
    idDetection = models.AutoField(primary_key=True)

    # Nom de l'objet identifié par Gemini.
    # Exemple : Bouteille, Canette, Journal...
    objet = models.CharField(max_length=100)

    # Niveau de confiance retourné par l'IA.
    confiance = models.FloatField()

    # Analyse IA à laquelle cette détection appartient.
    idAnalyse = models.ForeignKey(AnalyseIA, on_delete=models.CASCADE, related_name='detections')

    # Type de déchet officiel provenant du référentiel Django.
    # Exemple : Plastique, Métal, Verre...
    idTypeDechet = models.ForeignKey(TypeDechet, on_delete=models.SET_NULL, null=True, related_name='detections')


    def __str__(self):
        return f"{self.objet} - {self.idTypeDechet}"