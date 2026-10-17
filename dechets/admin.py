from django.contrib import admin
from .models import PanierDechet

# Rend le stock consultable depuis l'administration Django.
admin.site.register(PanierDechet)
