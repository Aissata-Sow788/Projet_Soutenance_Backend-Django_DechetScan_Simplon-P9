from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import Utilisateur
from .serializers import InscriptionSerializer, ConnexionSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated
from .serializers import UtilisateurSerializer
from rest_framework.views import APIView
from .permissions import IsAdmin 
from .serializers import GestionUtilisateurSerializer
from rest_framework.decorators import action



class InscriptionViewSet(viewsets.ModelViewSet):
    # Récupère les utilisateurs depuis la base de données
    queryset = Utilisateur.objects.all()

    # Serializer utilisé pour valider les données d'inscription
    serializer_class = InscriptionSerializer

    # Pour l'inscription, on autorise uniquement les requêtes POST
    http_method_names = ['post']

    def create(self, request, *args, **kwargs):
        # Récupère les données envoyées par le client
        serializer = self.get_serializer(data=request.data)

        # Vérifie les données avec le serializer
        # Si elles sont incorrectes, une erreur 400 est automatiquement retournée
        serializer.is_valid(raise_exception=True)

        # Crée l'utilisateur dans la base de donnee
        utilisateur = serializer.save()

        # Retourne une réponse après la création du compte.
        return Response(
            {
                'message': 'Compte créé avec succès.',
                'email': utilisateur.email,
                'role': utilisateur.role
            },
            status=status.HTTP_201_CREATED
        )
class ConnexionViewSet(TokenObtainPairView):
    # Vue permettant de connecter l'utilisateur
    # et de générer les tokens JWT.

    serializer_class = ConnexionSerializer

class UtilisateurConnecteView(APIView):
     # Cette permission oblige l'utilisateur
     #  # à fournir un token JWT valide. 
    permission_classes = [IsAuthenticated]

    def get(self, request): 
        # request.user contient automatiquement
         # l'utilisateur correspondant au token JWT.
        serializer = UtilisateurSerializer(request.user) 

         # Retourne les informations de l'utilisateur connecté. 
        return Response(serializer.data)


class GestionUtilisateurViewSet(viewsets.ReadOnlyModelViewSet):
    # Récupère tous les utilisateurs depuis la base de données.
    queryset = Utilisateur.objects.all()

    # Serializer utilisé pour afficher les utilisateurs.
    serializer_class = GestionUtilisateurSerializer

    # L'utilisateur doit être connecté avec un JWT
    # et avoir le rôle administrateur.
    permission_classes = [IsAuthenticated, IsAdmin]

    @action(detail=True, methods=['patch'])
    def toggle_active(self, request, pk=None):
        # Récupère l'utilisateur correspondant à l'identifiant
        # présent dans l'URL.
        utilisateur = self.get_object()

        # Inverse l'état actuel du compte.
        utilisateur.is_active = not utilisateur.is_active

        # Enregistre le nouvel état dans la base de données.
        utilisateur.save()

        # Retourne le nouvel état du compte.
        return Response({
            'message': 'Statut de l’utilisateur modifié avec succès.',
            'is_active': utilisateur.is_active
        })

