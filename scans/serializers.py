from rest_framework import serializers

from .models import ScanDechet, AnalyseIA, DetectionIA
from dechets.serializers import TypeDechetSerializer


class DetectionIASerializer(serializers.ModelSerializer):
    # Lecture : affiche les informations du type de déchet
    # provenant du référentiel Django.
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

        # Ces champs sont générés automatiquement
        # ou définis par le serveur.
        read_only_fields = ['idScan', 'idUtilisateur', 'dateScan']


class ScanDechetCreationSerializer(serializers.ModelSerializer):
    # À la création, le citoyen envoie uniquement la photo.
    photoUrl = serializers.ImageField(write_only=True)

    class Meta:
        model = ScanDechet
        fields = ['photoUrl']

class ScanDechetAdminSerializer(serializers.ModelSerializer):
    citoyen = serializers.SerializerMethodField()
    analyseIA = AnalyseIASerializer(read_only=True)
    nombreScans = serializers.SerializerMethodField()

    class Meta:
        model = ScanDechet
        fields = [
            'idScan',
            'dateScan',
            'photoUrl',
            'idUtilisateur',
            'citoyen',
            'analyseIA',
            'nombreScans',
        ]

    def get_citoyen(self, obj):
        utilisateur = obj.idUtilisateur

        if utilisateur is None:
            return None

        return {
            'id': utilisateur.pk,

            # Récupère prenom si ton modèle utilise "prenom",
            # sinon utilise "first_name".
            'prenom': getattr(
                utilisateur,
                'prenom',
                getattr(utilisateur, 'first_name', '')
            ),

            # Récupère nom si ton modèle utilise "nom",
            # sinon utilise "last_name".
            'nom': getattr(
                utilisateur,
                'nom',
                getattr(utilisateur, 'last_name', '')
            ),

            'email': getattr(utilisateur, 'email', ''),
        }

    def get_nombreScans(self, obj):
        # ------------------------------------------------------
        # SCAN ANONYME
        # ------------------------------------------------------
        # Aucun utilisateur associé au scan.
        if obj.idUtilisateur is None:
            return 1

        # ------------------------------------------------------
        # UTILISATEUR CONNECTÉ
        # ------------------------------------------------------
        # Compte tous les scans appartenant à cet utilisateur.
        return ScanDechet.objects.filter(
            idUtilisateur=obj.idUtilisateur
        ).count()