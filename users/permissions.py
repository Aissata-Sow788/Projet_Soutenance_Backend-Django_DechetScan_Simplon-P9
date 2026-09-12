
from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    # Vérifie que l'utilisateur connecté possède
    # le rôle administrateur.
    def has_permission(self, request, view):

        # request.user représente l'utilisateur connecté
        # grâce à son token JWT.

        return (
            request.user.is_authenticated
            and request.user.role == 'admin'
        )

