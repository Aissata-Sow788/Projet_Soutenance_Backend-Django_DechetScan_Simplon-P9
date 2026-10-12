from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from collecteurs.models import Collecteur
from dechets.models import PanierDechet, PrixDechet, TypeDechet
from dechets.serializers import TypeDechetSerializer
from dechets.services import reserver_quantites_paniers

from .models import DetailVenteDechet, VenteDechet


class DetailVenteDechetSerializer(serializers.ModelSerializer):
    """Retourne le poids, le compte d'objets et le sous-total historique."""

    idTypeDechet = serializers.IntegerField(
        source='idPanier.idTypeDechet.idTypeDechet',
        read_only=True,
    )
    typeDechet = TypeDechetSerializer(source='idPanier.idTypeDechet', read_only=True)
    sousTotal = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    # Maintient la lecture du champ utilisé par les anciennes versions Angular.
    quantite = serializers.DecimalField(
        source='poidsKg',
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )

    class Meta:
        model = DetailVenteDechet
        fields = [
            'idDetail',
            'idPanier',
            'idTypeDechet',
            'typeDechet',
            'nombreObjets',
            'poidsKg',
            'quantite',
            'prixParKg',
            'sousTotal',
        ]


class VenteDechetSerializer(serializers.ModelSerializer):
    details = DetailVenteDechetSerializer(many=True, read_only=True)
    emailUtilisateur = serializers.EmailField(
        source='idUtilisateur.email',
        read_only=True,
        allow_null=True,
    )
    prenomUtilisateur = serializers.SerializerMethodField()
    nomUtilisateur = serializers.SerializerMethodField()
    nomCollecteur = serializers.CharField(
        source='idCollecteur.nomEntreprise',
        read_only=True,
        allow_null=True,
    )
    idTypeDechet = serializers.SerializerMethodField()
    typeDechet = serializers.SerializerMethodField()
    quantite = serializers.SerializerMethodField()
    poidsTotalKg = serializers.SerializerMethodField()
    nombreObjets = serializers.SerializerMethodField()

    class Meta:
        model = VenteDechet
        fields = [
            'idVente',
            'idUtilisateur',
            'emailUtilisateur',
            'prenomUtilisateur',
            'nomUtilisateur',
            'idCollecteur',
            'nomCollecteur',
            'idTypeDechet',
            'typeDechet',
            'quantite',
            'poidsTotalKg',
            'nombreObjets',
            'details',
            'prixPaye',
            'methodePaiement',
            'statutPaiement',
            'referencePaiement',
            'dateVente',
        ]
        read_only_fields = fields

    @staticmethod
    def get_prenomUtilisateur(obj):
        return obj.idUtilisateur.first_name if obj.idUtilisateur else ''

    @staticmethod
    def get_nomUtilisateur(obj):
        return obj.idUtilisateur.last_name if obj.idUtilisateur else ''

    @staticmethod
    def _details(obj):
        return list(obj.details.all())

    def get_idTypeDechet(self, obj):
        details = self._details(obj)
        return details[0].idPanier.idTypeDechet_id if len(details) == 1 else None

    def get_typeDechet(self, obj):
        details = self._details(obj)
        if len(details) != 1:
            return None
        return TypeDechetSerializer(details[0].idPanier.idTypeDechet).data

    def get_quantite(self, obj):
        # Le champ historique reste exprimé en kilogrammes pour compatibilité.
        return self.get_poidsTotalKg(obj)

    def get_poidsTotalKg(self, obj):
        return sum((detail.poidsKg for detail in self._details(obj)), Decimal('0'))

    def get_nombreObjets(self, obj):
        details = self._details(obj)
        # Les anciennes ventes n'avaient pas de compte d'objets fiable.
        if any(detail.nombreObjets is None for detail in details):
            return None
        return sum(detail.nombreObjets for detail in details)


class LigneVenteCreationSerializer(serializers.Serializer):
    """Valide le nombre d'objets sélectionné et leur poids mesuré."""

    idPanier = serializers.PrimaryKeyRelatedField(
        queryset=PanierDechet.objects.select_related('idTypeDechet')
    )
    nombreObjets = serializers.IntegerField(min_value=1, required=False)
    poidsKg = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal('0.001'),
        required=False,
    )
    # Compatibilité avec les clients qui transmettaient le poids comme quantité.
    quantite = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal('0.001'),
        required=False,
    )

    def validate(self, attrs):
        poids_saisi = attrs.pop('poidsKg', None)
        poids_historique = attrs.pop('quantite', None)
        poids = poids_saisi if poids_saisi is not None else poids_historique
        if poids is None:
            raise serializers.ValidationError({
                'poidsKg': 'Le poids réellement mesuré est obligatoire.'
            })
        panier = attrs['idPanier']
        attrs['poidsKg'] = poids
        # Sans champ de compte, un ancien client engage tout le stock restant.
        attrs['nombreObjets'] = attrs.get('nombreObjets') or panier.nombreDisponible
        if attrs['nombreObjets'] <= 0:
            raise serializers.ValidationError({
                'nombreObjets': 'Aucun objet disponible dans ce panier.'
            })
        return attrs


class VenteDechetCreationSerializer(serializers.Serializer):
    """Calcule le prix côté serveur et réserve plusieurs paniers atomiquement."""

    idCollecteur = serializers.PrimaryKeyRelatedField(
        queryset=Collecteur.objects.filter(statutValidation='valide')
    )
    details = LigneVenteCreationSerializer(many=True, required=False, min_length=1)

    # Compatibilité temporaire avec le formulaire actuel à catégorie unique.
    idTypeDechet = serializers.PrimaryKeyRelatedField(
        queryset=TypeDechet.objects.all(),
        required=False,
        write_only=True,
    )
    quantite = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal('0.001'),
        required=False,
        write_only=True,
    )
    prixPaye = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        write_only=True,
    )
    methodePaiement = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        lignes = attrs.get('details')
        type_dechet = attrs.get('idTypeDechet')
        quantite = attrs.get('quantite')

        if lignes is None:
            if type_dechet is None or quantite is None:
                raise serializers.ValidationError(
                    {'details': 'Fournissez les paniers et quantités à vendre.'}
                )
            try:
                panier = PanierDechet.objects.get(
                    idUtilisateur=self.context['request'].user,
                    idTypeDechet=type_dechet,
                )
            except PanierDechet.DoesNotExist:
                raise serializers.ValidationError(
                    {'idTypeDechet': 'Aucun panier correspondant à cette catégorie.'}
                )
            lignes = [{
                'idPanier': panier,
                'nombreObjets': panier.nombreDisponible,
                'poidsKg': quantite,
            }]

        panier_ids = [ligne['idPanier'].pk for ligne in lignes]
        if len(panier_ids) != len(set(panier_ids)):
            raise serializers.ValidationError(
                {'details': 'Un panier ne peut apparaître qu’une seule fois.'}
            )
        attrs['details'] = lignes
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        utilisateur = validated_data['idUtilisateur']
        collecteur = validated_data['idCollecteur']
        lignes = validated_data['details']
        paniers = reserver_quantites_paniers(utilisateur, lignes)
        aujourd_hui = timezone.localdate()

        tarif_par_panier = {}
        montant_total = Decimal('0')
        for ligne in lignes:
            panier = paniers[ligne['idPanier'].pk]
            tarif = PrixDechet.objects.filter(
                idTypeDechet=panier.idTypeDechet,
                idCollecteur=collecteur,
                dateDebut__lte=aujourd_hui,
            ).filter(
                Q(dateFin__isnull=True) | Q(dateFin__gte=aujourd_hui)
            ).order_by('-dateDebut', '-idPrix').first()
            if tarif is None:
                raise serializers.ValidationError({
                    'details': f"Aucun tarif actif pour {panier.idTypeDechet.nom}."
                })
            prix = Decimal(str(tarif.prixParKg)).quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP,
            )
            tarif_par_panier[panier.pk] = prix
            # Le tarif est copié sur le détail pour figer l'historique de vente.
            montant_total += ligne['poidsKg'] * prix

        montant_total = montant_total.quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )
        vente = VenteDechet.objects.create(
            idUtilisateur=utilisateur,
            idCollecteur=collecteur,
            prixPaye=montant_total,
            methodePaiement=validated_data.get('methodePaiement', ''),
        )
        DetailVenteDechet.objects.bulk_create([
            DetailVenteDechet(
                idVente=vente,
                idPanier=paniers[ligne['idPanier'].pk],
                poidsKg=ligne['poidsKg'],
                nombreObjets=ligne['nombreObjets'],
                prixParKg=tarif_par_panier[ligne['idPanier'].pk],
            )
            for ligne in lignes
        ])
        return vente


class VenteDechetStatutSerializer(serializers.ModelSerializer):
    class Meta:
        model = VenteDechet
        fields = ['statutPaiement']
