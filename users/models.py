from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


# Manager personnalisé adapté à notre utilisateur sans champ username.
class UtilisateurManager(BaseUserManager):

    # Crée un utilisateur normal avec l'adresse email comme identifiant.
    def create_user(self, email, password=None, **extra_fields):

        # Vérifie qu'une adresse email a bien été fournie.
        if not email:
            raise ValueError("L'adresse email est obligatoire.")

        # Normalise l'adresse email.
        email = self.normalize_email(email)

        # Crée l'utilisateur avec les informations fournies.
        utilisateur = self.model(
            email=email,
            **extra_fields
        )

        # Hache le mot de passe avant de l'enregistrer.
        utilisateur.set_password(password)

        # Enregistre l'utilisateur dans la base de données.
        utilisateur.save(using=self._db)

        # Retourne l'utilisateur créé.
        return utilisateur

    # Crée un superutilisateur avec les droits administrateur.
    def create_superuser(self, email, password=None, **extra_fields):

        # Active les permissions administrateur.
        extra_fields.setdefault('is_staff', True)

        # Active les permissions de superutilisateur.
        extra_fields.setdefault('is_superuser', True)

        # Vérifie que les permissions sont correctement configurées.
        if extra_fields.get('is_staff') is not True:
            raise ValueError("Le superutilisateur doit avoir is_staff=True.")

        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Le superutilisateur doit avoir is_superuser=True.")

        # Utilise create_user() pour créer le compte.
        return self.create_user(
            email=email,
            password=password,
            **extra_fields
        )



class Utilisateur(AbstractUser):  

    # Supprime le champ username hérité de AbstractUser.
    username = None

    # Indique que l'email sera utilisé pour se connecter.
    USERNAME_FIELD = 'email'

    # Aucun autre champ n'est obligatoire lors de la création
    # d'un utilisateur avec la commande createsuperuser.
    REQUIRED_FIELDS = []

    ROLE_CHOICES = [
        ('citoyen', 'Citoyen'),
        ('admin', 'Administrateur'),
    ]

    email = models.EmailField(unique=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='citoyen')

    # Ville de résidence de l'utilisateur. 
    ville = models.CharField( max_length=100, blank=True )

    # Numéro de téléphone de l'utilisateur.
    # Il doit être unique pour permettre la connexion avec le téléphone.
    telephone = models.CharField(max_length=20, unique=True, blank=True, null=True)

    # Utilise notre manager personnalisé.
    objects = UtilisateurManager()

    def __str__(self):
        return f"{self.email} - {self.role}"