from rest_framework import serializers
from .models import DemandeCollecte
from dechets.serializers import TypeDechetSerializer
from dechets.models import TypeDechet


class CollecteResumeSuiviSerializer(serializers.Serializer):
    """
    Serializer léger pour afficher le résumé de la collecte
    liée à une demande dans la page 'Suivi de ma demande'.
    Expose uniquement les infos nécessaires au citoyen :
    - qui va venir (nom, prénom, téléphone du collecteur)
    - quand (datePlanifiee)
    - quel statut
    """

    idCollecte = serializers.IntegerField()
    datePlanifiee = serializers.DateTimeField()
    statut = serializers.CharField()

    # Infos du collecteur assigné.
    prenomCollecteur = serializers.SerializerMethodField()
    nomCollecteur = serializers.SerializerMethodField()
    telephoneCollecteur = serializers.SerializerMethodField()
    nomEntrepriseCollecteur = serializers.SerializerMethodField()

    def get_prenomCollecteur(self, obj):
        """Retourne le prénom du collecteur assigné."""
        if obj.idCollecteur and obj.idCollecteur.idUtilisateur:
            return obj.idCollecteur.idUtilisateur.first_name
        return None

    def get_nomCollecteur(self, obj):
        """Retourne le nom du collecteur assigné."""
        if obj.idCollecteur and obj.idCollecteur.idUtilisateur:
            return obj.idCollecteur.idUtilisateur.last_name
        return None

    def get_telephoneCollecteur(self, obj):
        """Retourne le téléphone professionnel du collecteur."""
        if obj.idCollecteur:
            return obj.idCollecteur.telephoneProfessionnel
        return None

    def get_nomEntrepriseCollecteur(self, obj):
        """Retourne le nom de l'entreprise du collecteur."""
        if obj.idCollecteur:
            return obj.idCollecteur.nomEntreprise
        return None


class CollecteurAttribueSerializer(serializers.Serializer):
    """
    Serializer léger pour exposer les infos du collecteur
    attribué directement sur la demande.
    Utilisé dans DemandeCollecteSerializer pour que le citoyen
    sache quelle entreprise a accepté sa demande de ramassage.
    """

    idCollecteur = serializers.IntegerField()
    nomEntreprise = serializers.CharField()
    telephoneProfessionnel = serializers.CharField()
    zoneIntervention = serializers.CharField()

    # Prénom et nom du représentant du collecteur.
    prenom = serializers.SerializerMethodField()
    nom = serializers.SerializerMethodField()

    def get_prenom(self, obj):
        """Retourne le prénom de l'utilisateur lié au collecteur."""
        if obj.idUtilisateur:
            return obj.idUtilisateur.first_name
        return None

    def get_nom(self, obj):
        """Retourne le nom de l'utilisateur lié au collecteur."""
        if obj.idUtilisateur:
            return obj.idUtilisateur.last_name
        return None


class DemandeCollecteSerializer(serializers.ModelSerializer):
    """
    Serializer de lecture pour DemandeCollecte.
    Affiche le détail complet du type de déchet concerné,
    les informations de l'utilisateur qui a soumis la demande,
    le collecteur attribué (si la demande a été acceptée),
    et la collecte liée (pour la page suivi du citoyen).
    """

    # Affiche le type de déchet en entier (nom, description, conseil).
    typeDechet = TypeDechetSerializer(source='idTypeDechet', read_only=True)

    # Affiche l'email du citoyen qui a soumis la demande.
    emailUtilisateur = serializers.EmailField(
        source='idUtilisateur.email',
        read_only=True
    )

    # Affiche le prénom du citoyen.
    prenomUtilisateur = serializers.CharField(
        source='idUtilisateur.first_name',
        read_only=True
    )

    # Affiche le nom du citoyen.
    nomUtilisateur = serializers.CharField(
        source='idUtilisateur.last_name',
        read_only=True
    )

    # Affiche le téléphone du citoyen.
    telephoneUtilisateur = serializers.CharField(
        source='idUtilisateur.telephone',
        read_only=True
    )

    # Inclut les infos du collecteur attribué à cette demande.
    # NULL tant qu'aucun collecteur n'a accepté (statut en_attente).
    collecteurAttribue = serializers.SerializerMethodField()

    def get_collecteurAttribue(self, obj):
        """
        Retourne les infos du collecteur qui a accepté la demande.
        NULL si la demande est encore en_attente.
        """
        if not obj.collecteurAttribue:
            return None
        return CollecteurAttribueSerializer(obj.collecteurAttribue).data

    # Inclut le résumé de la collecte liée pour la page suivi.
    # NULL si aucun collecteur n'a encore planifié la collecte.
    collecte = serializers.SerializerMethodField()

    def get_collecte(self, obj):
        """
        Retourne la première collecte liée à cette demande.
        C'est cette collecte qui contient la date planifiée de passage.
        """
        collecte = obj.collectes.select_related(
            'idCollecteur__idUtilisateur'
        ).first()

        if not collecte:
            return None

        return CollecteResumeSuiviSerializer(collecte).data

    class Meta:
        model = DemandeCollecte
        fields = [
            'idDemande',
            'idUtilisateur',
            'emailUtilisateur',
            'prenomUtilisateur',
            'nomUtilisateur',
            'telephoneUtilisateur',
            'idTypeDechet',
            'typeDechet',
            'quantite',
            'typeDemande',
            'prixPropose',
            'quartier',
            'latitude',
            'longitude',
            'dateDemande',
            'dateSouhaitee',
            'statut',
            # Collecteur qui a accepté la demande (null si en_attente).
            'collecteurAttribue',
            # Collecte planifiée liée (pour la page suivi citoyen).
            'collecte',
        ]
        read_only_fields = [
            'idDemande',
            'idUtilisateur',
            'emailUtilisateur',
            'prenomUtilisateur',
            'nomUtilisateur',
            'telephoneUtilisateur',
            'typeDechet',
            'dateDemande',
            'collecteurAttribue',
            'collecte',
        ]


class DemandeCollecteCreationSerializer(serializers.ModelSerializer):
    """
    Serializer d'écriture pour créer une demande de collecte.
    L'idUtilisateur est affecté automatiquement dans la vue
    à partir de l'utilisateur connecté (request.user).
    idTypeDechet accepte un entier (id du type de déchet).
    """

    # Accepte l'id du type de déchet à l'écriture.
    idTypeDechet = serializers.PrimaryKeyRelatedField(
        queryset=TypeDechet.objects.all()
    )

    # Coordonnées GPS envoyées automatiquement par le navigateur Angular.
    # required=False : si l'utilisateur refuse la géolocalisation,
    # la demande peut quand même être soumise.
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)

    class Meta:
        model = DemandeCollecte
        fields = [
            'idTypeDechet',
            'quantite',
            'typeDemande',
            'prixPropose',
            'quartier',
            'latitude',
            'longitude',
            'dateSouhaitee',
        ]


class DemandeCollecteStatutSerializer(serializers.ModelSerializer):
    """
    Serializer dédié à la mise à jour du statut d'une demande.
    Utilisé par les collecteurs pour accepter une demande
    et par les admins pour changer le statut.
    """

    class Meta:
        model = DemandeCollecte
        fields = ['statut']
