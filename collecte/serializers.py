from rest_framework import serializers
from .models import PointCollecte, Collecte
from dechets.serializers import TypeDechetSerializer
from dechets.models import TypeDechet


class PointCollecteSerializer(serializers.ModelSerializer):
    # Lecture : affiche les types de déchets acceptés en entier (nom, description...)
    dechetsAcceptes = TypeDechetSerializer(many=True, read_only=True)

    class Meta:
        model = PointCollecte
        fields = [
            'idPoint', 'nom', 'ville', 'latitude', 'longitude',
            'statut', 'heureOuverture', 'heureFermeture', 'dechetsAcceptes', 'gerePar']
        read_only_fields = ['gerePar']


class PointCollecteEcritureSerializer(serializers.ModelSerializer):
    # Écriture : on envoie juste une liste d'id de TypeDechet (ex: [1, 3, 4])
    dechetsAcceptes = serializers.PrimaryKeyRelatedField(
        many=True, queryset=TypeDechet.objects.all()
    )

    class Meta:
        model = PointCollecte
        fields = [
            'nom', 'ville', 'latitude', 'longitude',
            'statut', 'heureOuverture', 'heureFermeture', 'dechetsAcceptes'
        ]


class CollecteSerializer(serializers.ModelSerializer):
    """
    Serializer de lecture pour Collecte.
    Affiche les informations complètes de la collecte :
    - nom de l'entreprise du collecteur
    - nom du point de collecte concerné (si applicable)
    - id de la demande liée (si applicable)
    """

    # Affiche le nom de l'entreprise du collecteur.
    nomCollecteur = serializers.CharField(
        source='idCollecteur.nomEntreprise',
        read_only=True
    )

    # Affiche le nom du point de collecte (si la collecte est liée à un point).
    nomPoint = serializers.CharField(
        source='idPoint.nom',
        read_only=True
    )

    nomDechet = serializers.SerializerMethodField()
    quantite = serializers.SerializerMethodField()
    prenomCitoyen = serializers.SerializerMethodField()
    nomCitoyen = serializers.SerializerMethodField()
    zone = serializers.SerializerMethodField()

    def get_nomDechet(self, obj):
        demande = obj.idDemande
        if demande and demande.idTypeDechet:
            return demande.idTypeDechet.nom
        return None

    def get_quantite(self, obj):
        if obj.quantiteRecuperee is not None:
            return obj.quantiteRecuperee
        return obj.idDemande.quantite if obj.idDemande else None

    def get_prenomCitoyen(self, obj):
        demande = obj.idDemande
        return demande.idUtilisateur.first_name if demande and demande.idUtilisateur else None

    def get_nomCitoyen(self, obj):
        demande = obj.idDemande
        return demande.idUtilisateur.last_name if demande and demande.idUtilisateur else None

    def get_zone(self, obj):
        demande = obj.idDemande
        if demande and demande.quartier.strip():
            return demande.quartier
        return obj.idPoint.ville if obj.idPoint else None

    class Meta:
        model = Collecte
        fields = [
            'idCollecte',
            'idCollecteur',
            'nomCollecteur',
            'idPoint',
            'nomPoint',
            'idDemande',
            'nomDechet',
            'quantite',
            'prenomCitoyen',
            'nomCitoyen',
            'zone',
            'datePlanifiee',
            'statut',
            'dateRealisation',
            'quantiteRecuperee',
        ]
        # Ces champs sont auto-générés ou calculés.
        read_only_fields = [
            'idCollecte',
            'nomCollecteur',
            'nomPoint',
        ]


class CollecteCreationSerializer(serializers.ModelSerializer):
    """
    Serializer d'écriture pour créer une collecte.
    idCollecteur est affecté automatiquement dans la vue
    depuis le profil collecteur de l'utilisateur connecté.
    """

    class Meta:
        model = Collecte
        fields = [
            'idPoint',
            'idDemande',
            'datePlanifiee',
            'statut',
        ]


class CollecteStatutSerializer(serializers.ModelSerializer):
    """
    Serializer dédié à la mise à jour du statut et des données
    de réalisation d'une collecte (dateRealisation, quantiteRecuperee).
    """

    class Meta:
        model = Collecte
        fields = [
            'statut',
            'dateRealisation',
            'quantiteRecuperee',
        ]