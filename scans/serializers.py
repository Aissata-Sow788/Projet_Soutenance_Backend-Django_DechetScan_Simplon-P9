from rest_framework import serializers
from .models import ScanDechet, AnalyseIA
from dechets.serializers import TypeDechetSerializer


class AnalyseIASerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyseIA
        fields = ['idAnalyse', 'resultat', 'scoreConfiance', 'dateAnalyse']


class ScanDechetSerializer(serializers.ModelSerializer):
    # Lecture : affiche le type de déchet et l'analyse en entier, pas juste leur id
    idTypeDechet = TypeDechetSerializer(read_only=True)
    analyseIA = AnalyseIASerializer(read_only=True)

    class Meta:
        model = ScanDechet
        fields = ['idScanDechet', 'dateScan', 'photoUrl', 'idUtilisateur', 'idTypeDechet', 'analyseIA']
        read_only_fields = ['idUtilisateur', 'dateScan']


class ScanDechetCreationSerializer(serializers.ModelSerializer):
    # Écriture : à l'envoi d'une photo, seul le fichier est nécessaire
    # (idUtilisateur vient de la requête authentifiée, typeDechet/analyseIA sont calculés par l'IA après coup)
    photo = serializers.ImageField(write_only=True)

    class Meta:
        model = ScanDechet
        fields = ['photo']