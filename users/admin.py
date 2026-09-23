from django.contrib import admin

from .models import Utilisateur


# Enregistre le modèle Utilisateur dans l'interface Django Admin.
@admin.register(Utilisateur)
class UtilisateurAdmin(admin.ModelAdmin):

    # Colonnes affichées dans la liste des utilisateurs.
    list_display = ('id', 'first_name', 'last_name', 'email', 'telephone', 'ville', 'role', 'is_active', 'date_joined')

    # Champs permettant de rechercher rapidement un utilisateur.
    search_fields = ('email', 'last_name', 'first_name',)

    # Filtres disponibles dans la colonne de droite.
    list_filter = ('role', 'is_active')