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
        identifiant = attrs.get('identifiant')

        # Récupère le mot de passe saisi.
        password = attrs.get('password')

        # Recherche l'utilisateur avec son email.
        utilisateur = Utilisateur.objects.filter(
            email=identifiant
        ).first()

        # Si aucun utilisateur n'est trouvé avec l'email,
        # recherche avec le numéro de téléphone.
        if utilisateur is None:
            utilisateur = Utilisateur.objects.filter(
                telephone=identifiant
            ).first()

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

        # Génère le token JWT pour l'utilisateur.
        refresh = self.get_token(utilisateur)

        # Retourne les tokens JWT.
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token)
        }


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