from django.db import models
from django.conf import settings
from dechets.models import TypeDechet


class ScanDechet(models.Model):
    idScan = models.AutoField(primary_key=True)
    dateScan = models.DateTimeField(auto_now_add=True)
    photoUrl = models.ImageField(upload_to='scans/')

    idUtilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='scans')

    idTypeDechet = models.ForeignKey(TypeDechet, on_delete=models.SET_NULL, null=True, related_name='scans')

    def __str__(self):
        return f"Scan #{self.idScan} - {self.dateScan.date()}"


class AnalyseIA(models.Model):
    idAnalyse = models.AutoField(primary_key=True)
    resultat = models.CharField(max_length=100)  # label brut renvoyé par l'IA
    scoreConfiance = models.FloatField()
    dateAnalyse = models.DateTimeField(auto_now_add=True)

    # Relation 1-1 "est analysé par"
    scan = models.OneToOneField(ScanDechet, on_delete=models.CASCADE, related_name='analyseIA')

    def __str__(self):
        return f"Analyse #{self.idAnalyse} ({self.resultat})"