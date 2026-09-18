from rest_framework import serializers

from .models import ScanDechet, AnalyseIA
from dechets.serializers import TypeDechetSerializer


class AnalyseIASerializer(serializers.ModelSerializer):
    # Retourne le type de déchet détecté avec son conseil de tri.
    idTypeDechet = TypeDechetSerializer(read_only=True)

    class Meta:
        model = AnalyseIA
        fields = ['idAnalyse', 'resultat', 'scoreConfiance', 'dateAnalyse', 'idScan', 'idTypeDechet',]


class ScanDechetSerializer(serializers.ModelSerializer):
    # Retourne l'analyse IA associée au scan.
    analyseIA = AnalyseIASerializer(read_only=True)

    class Meta:
        model = ScanDechet
        fields = ['idScan', 'dateScan', 'photoUrl', 'idUtilisateur', 'analyseIA',]

        # Ces champs sont générés automatiquement ou définis par le serveur.
        read_only_fields = ['idScan', 'idUtilisateur', 'dateScan',]

class ScanDechetCreationSerializer(serializers.ModelSerializer):
    # À la création, le citoyen envoie uniquement la photo.
    # L'utilisateur connecté est récupéré automatiquement.
    photoUrl = serializers.ImageField(write_only=True)

    class Meta:
        model = ScanDechet
        fields = ['photoUrl']