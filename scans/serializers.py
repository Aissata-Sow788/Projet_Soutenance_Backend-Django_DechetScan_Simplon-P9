from rest_framework import serializers
from .models import ScanDechet, AnalyseIA
from dechets.serializers import TypeDechetSerializer


class AnalyseIASerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyseIA
        fields = ['idAnalyse', 'resultat', 'scoreConfiance', 'dateAnalyse']


class ScanDechetSerializer(serializers.ModelSerializer):
    # Lecture : affiche le type de déchet et l'analyse complète
    idTypeDechet = TypeDechetSerializer(read_only=True)
    analyseIA = AnalyseIASerializer(read_only=True)

    class Meta:
        model = ScanDechet
        fields = ['idScan', 'dateScan', 'photoUrl', 'idUtilisateur', 'idTypeDechet', 'analyseIA']
        read_only_fields = ['idScan', 'idUtilisateur', 'dateScan']


class ScanDechetCreationSerializer(serializers.ModelSerializer):
    # À la création, le citoyen envoie uniquement la photo.
    # L'utilisateur connecté est récupéré automatiquement.
    photoUrl = serializers.ImageField(write_only=True)

    class Meta:
        model = ScanDechet
        fields = ['photoUrl']