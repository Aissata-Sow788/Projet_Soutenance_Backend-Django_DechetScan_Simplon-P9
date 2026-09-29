from django.db import models
from django.conf import settings


class Collecteur(models.Model):
    """
    Représente un professionnel du recyclage enregistré sur la plateforme.
    Un Collecteur est toujours lié à un Utilisateur existant (idUtilisateur).
    Il doit être validé par un administrateur avant de pouvoir opérer
    (statutValidation).
    Ce modèle est distinct de Utilisateur.is_active :
    - is_active contrôle l'accès au compte (connexion).
    - statutValidation contrôle le processus métier de validation du collecteur.
    """

    # Choix possibles pour le statut de validation du collecteur.
    STATUT_VALIDATION_CHOICES = [
        ('en_attente', 'En attente'),
        ('valide', 'Validé'),
        ('rejete', 'Rejeté'),
    ]

    idCollecteur = models.AutoField(primary_key=True)

    # Lien vers le compte utilisateur du collecteur.
    # Un utilisateur ne peut être collecteur qu'une seule fois (OneToOne).
    idUtilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='collecteur'
    )

    # Nom de l'entreprise de collecte (optionnel si indépendant).
    nomEntreprise = models.CharField(max_length=150, blank=True)

    # Numéro de téléphone professionnel, différent du téléphone personnel
    # stocké dans Utilisateur.telephone.
    telephoneProfessionnel = models.CharField(max_length=20, blank=True)

    # Zone géographique d'intervention du collecteur
    # (ex: "Dakar", "Pikine", "Guédiawaye").
    # Différent de Utilisateur.ville qui indique où habite l'utilisateur.
    zoneIntervention = models.CharField(max_length=150, blank=True)

    # Statut de validation par un administrateur.
    # en_attente : dossier soumis, pas encore traité.
    # valide : collecteur autorisé à opérer sur la plateforme.
    # rejete : dossier refusé par l'admin.
    statutValidation = models.CharField(
        max_length=20,
        choices=STATUT_VALIDATION_CHOICES,
        default='en_attente'
    )

    # Date d'inscription du collecteur sur la plateforme.
    dateInscription = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nomEntreprise or self.idUtilisateur.email} ({self.statutValidation})"


class AbonnementCollecteur(models.Model):
    """
    Représente l'abonnement souscrit par un collecteur pour accéder
    aux fonctionnalités premium de la plateforme.
    Un collecteur peut avoir plusieurs abonnements dans le temps
    (historique des abonnements).
    """

    # Choix possibles pour le statut de paiement de l'abonnement.
    STATUT_PAIEMENT_CHOICES = [
        ('en_attente', 'En attente'),
        ('paye', 'Payé'),
        ('echoue', 'Échoué'),
        ('annule', 'Annulé'),
    ]

    PLAN_CHOICES = [
        ('essentiel', 'Essentiel'),
        ('professionnel', 'Professionnel'),
        ('entreprise', 'Entreprise'),
    ]

    idAbonnement = models.AutoField(primary_key=True)

    # Collecteur auquel cet abonnement appartient.
    # Si le collecteur est supprimé, ses abonnements le sont aussi.
    idCollecteur = models.ForeignKey(
        Collecteur,
        on_delete=models.CASCADE,
        related_name='abonnements'
    )

    # Date de début de validité de l'abonnement.
    dateDebut = models.DateField()

    # Date de fin de validité de l'abonnement.
    dateFin = models.DateField()

    # Statut du paiement de l'abonnement.
    statutPaiement = models.CharField(
        max_length=20,
        choices=STATUT_PAIEMENT_CHOICES,
        default='en_attente'
    )

    # Méthode de paiement utilisée (ex: "Wave", "Orange Money", "Carte bancaire").
    methodePaiement = models.CharField(max_length=50, blank=True)

    # Montant payé pour cet abonnement (en FCFA).
    montant = models.FloatField()

    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='essentiel')
    referencePaiement = models.CharField(max_length=100, unique=True, null=True, blank=True)
    tokenPayDunya = models.CharField(max_length=100, unique=True, null=True, blank=True)

    def __str__(self):
        return f"Abonnement #{self.idAbonnement} - {self.idCollecteur} ({self.statutPaiement})"
