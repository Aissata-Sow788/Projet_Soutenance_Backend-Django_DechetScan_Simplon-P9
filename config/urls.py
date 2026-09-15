"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Imports nécessaires pour générer et afficher Swagger
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/scans/', include('scans.urls')),
    path('api/', include('collecte.urls')),

    # Authentification et gestion des utilisateurs
    path('api/auth/', include('users.urls')),
    path('api/', include('dechets.urls')),

    # Génère automatiquement le schéma OpenAPI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),

    # Interface graphique Swagger
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
]

# Gestion des fichiers média en développement
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )