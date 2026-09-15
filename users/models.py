from django.contrib.auth.models import AbstractUser
from django.db import models


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

    def __str__(self):
        return f"{self.email} - {self.role}"