from rest_framework import serializers
from .models import PointCollecte
from dechets.serializers import TypeDechetSerializer
from dechets.models import TypeDechet


class PointCollecteSerializer(serializers.ModelSerializer):
    # Lecture : affiche les types de déchets acceptés en entier (nom, description...)
    dechetsAcceptes = TypeDechetSerializer(many=True, read_only=True)

    class Meta:
        model = PointCollecte
        fields = [
            'idPoint', 'nom', 'ville', 'latitude', 'longitude',
            'statut', 'heureOuverture', 'heureFermeture', 'dechetsAcceptes', 'gerePar'
        ]
        read_only_fields = ['gerePar']


class PointCollecteEcritureSerializer(serializers.ModelSerializer):
    # Écriture : on envoie juste une liste d'id de TypeDechet (ex: [1, 3, 4])
    dechetsAcceptes = serializers.PrimaryKeyRelatedField(
        many=True, queryset=TypeDechet.objects.all()
    )

    class Meta:
        model = PointCollecte
        fields = [
            'nom', 'ville', 'latitude', 'longitude',
            'statut', 'heureOuverture', 'heureFermeture', 'dechetsAcceptes'
        ]