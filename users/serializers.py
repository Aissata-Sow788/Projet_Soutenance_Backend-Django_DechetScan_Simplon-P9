import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import translation
from rest_framework import serializers
from .models import Utilisateur
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from scans.models import ScanDechet


class InscriptionSerializer(serializers.ModelSerializer):
    # Deuxième champ de mot de passe utilisé uniquement
    # pour vérifier que l'utilisateur a bien saisi le même mot de passe deux fois.
    password2 = serializers.CharField(write_only=True)

    class Meta:
        # Le serializer utilise le modèle Utilisateur.
        model = Utilisateur

        # Champs qui seront acceptés lors de l'inscription.
        fields = ['first_name', 'last_name', 'email', 'telephone', 'password', 'password2', 'ville'
        ]

        # Le mot de passe peut être envoyé à l'API,
        # mais ne sera jamais retourné dans la réponse.
        extra_kwargs = {
            'password': {'write_only': True}
        }

    # Vérifie que les deux mots de passe sont identiques.
    def validate(self, data):

        # Compare le mot de passe avec sa confirmation.
        if data['password'] != data['password2']:
            raise serializers.ValidationError({
                'password': 'Les mots de passe ne correspondent pas.'
            })

        return data

    # Création de l'utilisateur après validation des données.
    def create(self, validated_data):

        # password2 sert uniquement à la vérification.
        # On le retire car il n'existe pas dans le modèle Utilisateur.
        validated_data.pop('password2')

        # Récupère le mot de passe avant la création.
        password = validated_data.pop('password')

        # create_user() crée l'utilisateur
        # et hache correctement le mot de passe.
        utilisateur = Utilisateur.objects.create_user(
            password=password,
            **validated_data
        )

        # Retourne l'utilisateur qui vient d'être créé.
        return utilisateur


class ConnexionSerializer(TokenObtainPairSerializer):
    # On indique à SimpleJWT que le champ utilisé
    # pour la connexion sera "identifiant".
    username_field = 'identifiant'

    # Champ permettant de saisir l'email ou le téléphone.
    identifiant = serializers.CharField()

    def validate(self, attrs):
        # Récupère l'identifiant saisi.
        identifiant = (attrs.get('identifiant') or '').strip()

        # Récupère le mot de passe saisi.
        password = attrs.get('password')

        # Recherche l'utilisateur avec son email.
        utilisateur = Utilisateur.objects.filter(
            email__iexact=identifiant
        ).first()

        # Ignore les espaces, indicatifs et séparateurs saisis autour du téléphone.
        if utilisateur is None:
            telephone_normalise = self.normaliser_telephone(identifiant)
            if telephone_normalise:
                utilisateurs_avec_telephone = Utilisateur.objects.exclude(
                    telephone__isnull=True
                ).exclude(telephone='')
                utilisateur = next(
                    (
                        candidat
                        for candidat in utilisateurs_avec_telephone
                        if self.normaliser_telephone(candidat.telephone)
                        == telephone_normalise
                    ),
                    None
                )

        # Si aucun compte ne correspond à l'identifiant.
        if utilisateur is None:
            raise serializers.ValidationError(
                'Email ou numéro de téléphone incorrect.'
            )

        # Vérifie le mot de passe.
        if not utilisateur.check_password(password):
            raise serializers.ValidationError(
                'Mot de passe incorrect.'
            )

        if not utilisateur.is_active:
            raise serializers.ValidationError(
                'Ce compte est désactivé.'
            )

        # Génère le token JWT pour l'utilisateur.
        refresh = self.get_token(utilisateur)

        # Retourne les tokens JWT.
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token)
        }

    @staticmethod
    def normaliser_telephone(telephone):
        """Convertit les variantes du numéro sénégalais en format comparable."""
        chiffres = re.sub(r'\D', '', telephone)
        if chiffres.startswith('221') and len(chiffres) == 12:
            return chiffres[3:]
        return chiffres


class UtilisateurSerializer(serializers.ModelSerializer):

    # Nombre total de scans réalisés par l'utilisateur.
    # Ce champ est calculé automatiquement à partir des scans liés.
    nombreScans = serializers.SerializerMethodField()

    # Serializer utilisé pour retourner les informations
    # de l'utilisateur actuellement connecté.
    class Meta:
        # Utilise le modèle Utilisateur.
        model = Utilisateur

        # Informations retournées pour l'utilisateur connecté.
        fields = ['id', 'first_name', 'last_name', 'email', 'telephone', 'ville', 'role', 'is_active', 'date_joined', 'last_login', 'nombreScans']

    def get_nombreScans(self, obj):
        # Compte tous les scans associés à cet utilisateur.
            return ScanDechet.objects.filter(
                idUtilisateur=obj
            ).count()


class ProfilUtilisateurModificationSerializer(serializers.ModelSerializer):
    """Autorise uniquement la modification des coordonnées du compte connecté."""

    telephone = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    class Meta:
        model = Utilisateur
        fields = ['first_name', 'last_name', 'email', 'telephone', 'ville']

    def validate_telephone(self, telephone):
        # La base autorise NULL mais exige l'unicité des numéros renseignés.
        return telephone or None


class ChangementMotDePasseSerializer(serializers.Serializer):
    ancienMotDePasse = serializers.CharField(write_only=True, trim_whitespace=False)
    nouveauMotDePasse = serializers.CharField(write_only=True, trim_whitespace=False)
    confirmationMotDePasse = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        utilisateur = self.context['request'].user
        if not utilisateur.check_password(attrs['ancienMotDePasse']):
            raise serializers.ValidationError({
                'ancienMotDePasse': 'Le mot de passe actuel est incorrect.'
            })

        if attrs['nouveauMotDePasse'] != attrs['confirmationMotDePasse']:
            raise serializers.ValidationError({
                'confirmationMotDePasse': 'Les mots de passe ne correspondent pas.'
            })

        with translation.override('fr'):
            try:
                validate_password(attrs['nouveauMotDePasse'], user=utilisateur)
            except DjangoValidationError as error:
                raise serializers.ValidationError({
                    'nouveauMotDePasse': list(error.messages)
                }) from error

        return attrs

    def save(self, **kwargs):
        utilisateur = self.context['request'].user
        utilisateur.set_password(self.validated_data['nouveauMotDePasse'])
        utilisateur.save(update_fields=['password'])
        return utilisateur


class GestionUtilisateurSerializer(serializers.ModelSerializer):

    # Nombre total de scans réalisés par l'utilisateur.
    nombreScans = serializers.SerializerMethodField()

    # Serializer utilisé par l'administrateur
    # pour consulter les informations des utilisateurs.
    class Meta:
        # Utilise notre modèle Utilisateur personnalisé.
        model = Utilisateur

        # Informations que l'administrateur peut consulter.
        fields = ['id', 'first_name', 'last_name', 'email', 'telephone', 'ville', 'role', 'is_active', 'date_joined', 'last_login', 'nombreScans']


            # Compte les scans associés à cet utilisateur.
    def get_nombreScans(self, obj):
        return ScanDechet.objects.filter(
            idUtilisateur=obj
        ).count()