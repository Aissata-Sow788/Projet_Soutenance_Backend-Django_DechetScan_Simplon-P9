from rest_framework import serializers

from .models import ScanDechet, AnalyseIA, DetectionIA
from dechets.serializers import TypeDechetSerializer


class DetectionIASerializer(serializers.ModelSerializer):
    # Lecture : affiche les informations du type de déchet associé.
    idTypeDechet = TypeDechetSerializer(read_only=True)

    class Meta:
        model = DetectionIA
        fields = ['idDetection', 'objet', 'confiance', 'idTypeDechet']


class AnalyseIASerializer(serializers.ModelSerializer):
    # Une analyse peut contenir plusieurs détections.
    detections = DetectionIASerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = AnalyseIA
        fields = ['idAnalyse', 'dateAnalyse', 'detections']


class ScanDechetSerializer(serializers.ModelSerializer):
    # Lecture : affiche l'analyse IA et toutes ses détections.
    analyseIA = AnalyseIASerializer(read_only=True)

    class Meta:
        model = ScanDechet
        fields = ['idScan', 'dateScan', 'photoUrl', 'idUtilisateur', 'analyseIA']
        read_only_fields = ['idScan', 'idUtilisateur', 'dateScan']


class ScanDechetCreationSerializer(serializers.ModelSerializer):
    # À la création, le citoyen envoie uniquement la photo.
    photoUrl = serializers.ImageField(write_only=True)

    class Meta:
        model = ScanDechet
        fields = ['photoUrl']