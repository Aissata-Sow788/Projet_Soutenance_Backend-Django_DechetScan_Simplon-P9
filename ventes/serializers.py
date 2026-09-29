from rest_framework import serializers
from .models import VenteDechet
from dechets.serializers import TypeDechetSerializer
from dechets.models import TypeDechet
from collecteurs.models import Collecteur


class VenteDechetSerializer(serializers.ModelSerializer):
    """
    Serializer de lecture pour VenteDechet.
    Affiche les informations complètes de la vente :
    - détail du type de déchet
    - email du citoyen vendeur
    - nom de l'entreprise du collecteur acheteur
    """

    # Affiche le type de déchet complet (nom, description, conseil).
    typeDechet = TypeDechetSerializer(source='idTypeDechet', read_only=True)

    # Affiche l'email du citoyen qui a vendu les déchets.
    emailUtilisateur = serializers.EmailField(
        source='idUtilisateur.email',
        read_only=True,
        allow_null=True,
    )

    prenomUtilisateur = serializers.SerializerMethodField()
    nomUtilisateur = serializers.SerializerMethodField()

    # Affiche le nom de l'entreprise du collecteur acheteur.
    nomCollecteur = serializers.CharField(
        source='idCollecteur.nomEntreprise',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = VenteDechet
        fields = [
            'idVente',
            'idUtilisateur',
            'emailUtilisateur',
            'prenomUtilisateur',
            'nomUtilisateur',
            'idCollecteur',
            'nomCollecteur',
            'idTypeDechet',
            'typeDechet',
            'quantite',
            'prixPaye',
            'methodePaiement',
            'statutPaiement',
            'referencePaiement',
            'dateVente',
        ]
        # Ces champs sont auto-générés ou calculés.
        read_only_fields = [
            'idVente',
            'dateVente',
            'emailUtilisateur',
            'nomCollecteur',
            'typeDechet',
        ]

    @staticmethod
    def get_prenomUtilisateur(obj):
        return obj.idUtilisateur.first_name if obj.idUtilisateur else ''

    @staticmethod
    def get_nomUtilisateur(obj):
        return obj.idUtilisateur.last_name if obj.idUtilisateur else ''


class VenteDechetCreationSerializer(serializers.ModelSerializer):
    """
    Serializer d'écriture pour créer une vente.
    - idUtilisateur : affecté automatiquement depuis request.user dans la vue.
    - idCollecteur  : fourni par l'utilisateur (id du collecteur acheteur).
    - idTypeDechet  : fourni par l'utilisateur (id du type de déchet vendu).
    """

    # Accepte l'id du collecteur acheteur.
    idCollecteur = serializers.PrimaryKeyRelatedField(
        queryset=Collecteur.objects.filter(statutValidation='valide')
    )

    # Accepte l'id du type de déchet vendu.
    idTypeDechet = serializers.PrimaryKeyRelatedField(
        queryset=TypeDechet.objects.all()
    )

    class Meta:
        model = VenteDechet
        fields = [
            'idCollecteur',
            'idTypeDechet',
            'quantite',
            'prixPaye',
            'methodePaiement',
            'statutPaiement',
            'referencePaiement',
        ]


class VenteDechetStatutSerializer(serializers.ModelSerializer):
    """
    Serializer dédié à la mise à jour du statut de paiement d'une vente.
    Utilisé par les admins pour changer le statut (paye, echoue, rembourse).
    """

    class Meta:
        model = VenteDechet
        fields = ['statutPaiement']
