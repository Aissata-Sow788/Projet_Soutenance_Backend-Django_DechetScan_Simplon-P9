from rest_framework import serializers
from .models import TypeDechet, ConseilTri, PrixDechet


class ConseilTriSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConseilTri
        fields = ['idConseil', 'consigne', 'idTypeDechet']


class TypeDechetSerializer(serializers.ModelSerializer):
    # Inclut le conseil de tri directement dans la réponse (relation 1-1)
    conseil = ConseilTriSerializer(read_only=True)

    class Meta:
        model = TypeDechet
        fields = ['idTypeDechet', 'nom', 'description', 'conseil']


class PrixDechetSerializer(serializers.ModelSerializer):
    """
    Serializer de lecture pour PrixDechet.
    Expose le champ calculé 'est_actif' (propriété du modèle)
    à la place du champ 'actif' supprimé.
    """

    # Champ calculé dynamiquement depuis la propriété du modèle.
    # read_only=True car ce n'est pas un champ stocké en base.
    est_actif = serializers.ReadOnlyField()

    # Affiche le nom du type de déchet pour plus de lisibilité.
    nomTypeDechet = serializers.CharField(
        source='idTypeDechet.nom',
        read_only=True
    )

    class Meta:
        model = PrixDechet
        fields = [
            'idPrix',
            'idTypeDechet',
            'nomTypeDechet',
            'prixParKg',
            'commission',
            'dateDebut',
            'dateFin',
            'est_actif',
        ]
        # idPrix est auto-généré, est_actif et nomTypeDechet sont calculés.
        read_only_fields = ['idPrix', 'est_actif', 'nomTypeDechet']