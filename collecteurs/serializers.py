from rest_framework import serializers
from users.models import Utilisateur
from .models import Collecteur, AbonnementCollecteur


class UtilisateurProfilCollecteurSerializer(serializers.ModelSerializer):
    telephone = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=20,
        validators=[],
    )

    class Meta:
        model = Utilisateur
        fields = ['first_name', 'last_name', 'email', 'telephone', 'ville']

    def validate_telephone(self, value):
        telephone = value.strip() if value else None
        if telephone and Utilisateur.objects.filter(
            telephone=telephone
        ).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError(
                'Ce numéro de téléphone est déjà utilisé.'
            )
        return telephone


class CollecteurProfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collecteur
        fields = [
            'nomEntreprise',
            'telephoneProfessionnel',
            'zoneIntervention',
            'statutValidation',
        ]
        read_only_fields = ['zoneIntervention', 'statutValidation']


class CollecteurSerializer(serializers.ModelSerializer):
    """
    Serializer de lecture pour Collecteur.
    Expose les informations du collecteur ainsi que l'email
    de l'utilisateur lié pour une meilleure lisibilité.
    """

    # Champ calculé : affiche l'email de l'utilisateur lié au collecteur.
    emailUtilisateur = serializers.EmailField(
        source='idUtilisateur.email',
        read_only=True
    )

    # Champ calculé : affiche le prénom de l'utilisateur lié.
    prenomUtilisateur = serializers.CharField(
        source='idUtilisateur.first_name',
        read_only=True
    )

    # Champ calculé : affiche le nom de l'utilisateur lié.
    nomUtilisateur = serializers.CharField(
        source='idUtilisateur.last_name',
        read_only=True
    )

    class Meta:
        model = Collecteur
        fields = [
            'idCollecteur',
            'idUtilisateur',
            'emailUtilisateur',
            'prenomUtilisateur',
            'nomUtilisateur',
            'nomEntreprise',
            'telephoneProfessionnel',
            'zoneIntervention',
            'statutValidation',
            'dateInscription',
        ]
        # Ces champs sont générés automatiquement ou calculés.
        read_only_fields = [
            'idCollecteur',
            'dateInscription',
            'emailUtilisateur',
            'prenomUtilisateur',
            'nomUtilisateur',
        ]


class CollecteurCreationSerializer(serializers.ModelSerializer):
    """
    Serializer d'écriture pour créer un profil Collecteur.
    L'idUtilisateur sera affecté automatiquement dans la vue
    à partir de l'utilisateur connecté (request.user).
    """

    class Meta:
        model = Collecteur
        fields = [
            'nomEntreprise',
            'telephoneProfessionnel',
            'zoneIntervention',
        ]


class CollecteurValidationSerializer(serializers.ModelSerializer):
    """
    Serializer dédié uniquement à la validation/rejet d'un collecteur.
    N'expose que le champ 'statutValidation'.
    Utilisé par l'action PATCH /api/collecteurs/{id}/valider/
    """

    class Meta:
        model = Collecteur
        fields = ['statutValidation']


class AbonnementCollecteurSerializer(serializers.ModelSerializer):
    """
    Serializer de lecture pour AbonnementCollecteur.
    Affiche les informations complètes d'un abonnement.
    """

    class Meta:
        model = AbonnementCollecteur
        fields = [
            'idAbonnement',
            'idCollecteur',
            'dateDebut',
            'dateFin',
            'statutPaiement',
            'methodePaiement',
            'montant',
            'plan',
            'referencePaiement',
        ]
        # idAbonnement est auto-généré.
        read_only_fields = ['idAbonnement', 'referencePaiement']


class AbonnementCollecteurCreationSerializer(serializers.ModelSerializer):
    """
    Serializer d'écriture pour créer un abonnement.
    idCollecteur sera affecté automatiquement dans la vue.
    """

    class Meta:
        model = AbonnementCollecteur
        fields = [
            'dateDebut',
            'dateFin',
            'statutPaiement',
            'methodePaiement',
            'montant',
        ]
