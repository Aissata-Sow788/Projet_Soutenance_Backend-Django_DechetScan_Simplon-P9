from django.db import models


class TypeDechet(models.Model):
    idTypeDechet = models.AutoField(primary_key=True)
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.nom


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