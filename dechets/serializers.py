from rest_framework import serializers
from .models import PanierDechet, TypeDechet, ConseilTri, PrixDechet


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
    idCollecteur = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = PrixDechet
        fields = [
            'idPrix',
            'idTypeDechet',
            'idCollecteur',
            'nomTypeDechet',
            'prixParKg',
            'commission',
            'dateDebut',
            'dateFin',
            'est_actif',
        ]
        # idPrix est auto-généré, est_actif et nomTypeDechet sont calculés.
        read_only_fields = ['idPrix', 'est_actif', 'nomTypeDechet']

    def validate_prixParKg(self, value):
        if value <= 0:
            raise serializers.ValidationError('Le prix doit être supérieur à zéro.')
        return value

    def validate_commission(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError('La commission doit être comprise entre 0 et 100 %.')
        return value

    def validate_idTypeDechet(self, value):
        if value.nom.strip().casefold() in {'inconnu', 'unknown'}:
            raise serializers.ValidationError(
                'Un tarif ne peut pas être associé à la catégorie Inconnu.'
            )
        return value

    def validate(self, attrs):
        date_debut = attrs.get('dateDebut', getattr(self.instance, 'dateDebut', None))
        date_fin = attrs.get('dateFin', getattr(self.instance, 'dateFin', None))
        if date_debut and date_fin and date_fin < date_debut:
            raise serializers.ValidationError({
                'dateFin': 'La date de fin doit être postérieure ou égale à la date de début.'
            })
        return attrs


class PanierDechetSerializer(serializers.ModelSerializer):
    """Expose un compte d'objets; les POST ajoutent ce compte au panier."""

    typeDechet = TypeDechetSerializer(source='idTypeDechet', read_only=True)
    idTypeDechet = serializers.PrimaryKeyRelatedField(
        queryset=TypeDechet.objects.all(),
        required=False,
    )

    class Meta:
        model = PanierDechet
        fields = [
            'idPanier',
            'idTypeDechet',
            'typeDechet',
            'nombreDisponible',
            'unite',
            'dateMiseAJour',
        ]
        read_only_fields = ['idPanier', 'typeDechet', 'dateMiseAJour', 'unite']

    def validate_nombreDisponible(self, value):
        if value < 0:
            raise serializers.ValidationError('Le nombre d’objets ne peut pas être négatif.')
        return value

    def validate_idTypeDechet(self, value):
        if (
            self.instance is not None
            and value != self.instance.idTypeDechet
        ):
            raise serializers.ValidationError(
                'La catégorie d’un panier ne peut pas être modifiée.'
            )
        return value
