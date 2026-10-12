from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from scans.models import ScanDechet
from dechets.models import PanierDechet, TypeDechet
from dechets.services import reserver_quantites_paniers
from dechets.serializers import TypeDechetSerializer
from .models import DetailDemandeCollecte, DemandeCollecte


class CollecteResumeSuiviSerializer(serializers.Serializer):
    """
    Serializer léger pour afficher le résumé de la collecte
    liée à une demande dans la page 'Suivi de ma demande'.
    Expose uniquement les infos nécessaires au citoyen :
    - qui va venir (nom, prénom, téléphone du collecteur)
    - quand (datePlanifiee)
    - quel statut
    """

    idCollecte = serializers.IntegerField()
    datePlanifiee = serializers.DateTimeField()
    statut = serializers.CharField()

    # Infos du collecteur assigné.
    prenomCollecteur = serializers.SerializerMethodField()
    nomCollecteur = serializers.SerializerMethodField()
    telephoneCollecteur = serializers.SerializerMethodField()
    nomEntrepriseCollecteur = serializers.SerializerMethodField()

    def get_prenomCollecteur(self, obj):
        """Retourne le prénom du collecteur assigné."""
        if obj.idCollecteur and obj.idCollecteur.idUtilisateur:
            return obj.idCollecteur.idUtilisateur.first_name
        return None

    def get_nomCollecteur(self, obj):
        """Retourne le nom du collecteur assigné."""
        if obj.idCollecteur and obj.idCollecteur.idUtilisateur:
            return obj.idCollecteur.idUtilisateur.last_name
        return None

    def get_telephoneCollecteur(self, obj):
        """Retourne le téléphone professionnel du collecteur."""
        if obj.idCollecteur:
            return obj.idCollecteur.telephoneProfessionnel
        return None

    def get_nomEntrepriseCollecteur(self, obj):
        """Retourne le nom de l'entreprise du collecteur."""
        if obj.idCollecteur:
            return obj.idCollecteur.nomEntreprise
        return None


class CollecteurAttribueSerializer(serializers.Serializer):
    """
    Serializer léger pour exposer les infos du collecteur
    attribué directement sur la demande.
    Utilisé dans DemandeCollecteSerializer pour que le citoyen
    sache quelle entreprise a accepté sa demande de ramassage.
    """

    idCollecteur = serializers.IntegerField()
    nomEntreprise = serializers.CharField()
    telephoneProfessionnel = serializers.CharField()
    zoneIntervention = serializers.CharField()

    # Prénom et nom du représentant du collecteur.
    prenom = serializers.SerializerMethodField()
    nom = serializers.SerializerMethodField()

    def get_prenom(self, obj):
        """Retourne le prénom de l'utilisateur lié au collecteur."""
        if obj.idUtilisateur:
            return obj.idUtilisateur.first_name
        return None

    def get_nom(self, obj):
        """Retourne le nom de l'utilisateur lié au collecteur."""
        if obj.idUtilisateur:
            return obj.idUtilisateur.last_name
        return None


class DemandeScanPhotoSerializer(serializers.ModelSerializer):
    """Expose la photo et la date d'un scan lié à une catégorie demandée."""

    class Meta:
        model = ScanDechet
        fields = ['idScan', 'dateScan', 'photoUrl']


class DetailDemandeCollecteSerializer(serializers.ModelSerializer):
    """Expose le compte d'objets et le poids réellement mesuré."""

    photos = serializers.SerializerMethodField()
    idTypeDechet = serializers.IntegerField(
        source='idPanier.idTypeDechet.idTypeDechet',
        read_only=True,
    )
    typeDechet = TypeDechetSerializer(source='idPanier.idTypeDechet', read_only=True)
    # Maintient la lecture du champ utilisé par les anciennes versions Angular.
    quantite = serializers.DecimalField(
        source='poidsKg',
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )

    class Meta:
        model = DetailDemandeCollecte
        fields = [
            'idDetail',
            'idPanier',
            'idTypeDechet',
            'typeDechet',
            'nombreObjets',
            'poidsKg',
            'quantite',
            'photos',
        ]

    def get_photos(self, obj):
        """Retourne les scans du citoyen correspondant à cette catégorie."""
        # Les miniatures sont nécessaires sur le détail, pas dans la liste.
        vue = self.context.get('view')
        if vue is not None and vue.action == 'list':
            return []

        demande = obj.idDemande
        return DemandeScanPhotoSerializer(
            ScanDechet.objects.filter(
                idUtilisateur=demande.idUtilisateur,
                dateScan__lte=demande.dateDemande,
                analyseIA__detections__idTypeDechet=obj.idPanier.idTypeDechet,
            ).distinct().order_by('-dateScan'),
            many=True,
            context=self.context,
        ).data


class DemandeCollecteSerializer(serializers.ModelSerializer):
    """
    Serializer de lecture pour DemandeCollecte.
    Affiche le détail complet du type de déchet concerné,
    les informations de l'utilisateur qui a soumis la demande,
    le collecteur attribué (si la demande a été acceptée),
    et la collecte liée (pour la page suivi du citoyen).
    """

    details = DetailDemandeCollecteSerializer(many=True, read_only=True)
    idTypeDechet = serializers.SerializerMethodField()
    typeDechet = serializers.SerializerMethodField()
    quantite = serializers.SerializerMethodField()
    poidsTotalKg = serializers.SerializerMethodField()
    nombreObjets = serializers.SerializerMethodField()

    # Affiche l'email du citoyen qui a soumis la demande.
    emailUtilisateur = serializers.EmailField(
        source='idUtilisateur.email',
        read_only=True
    )

    # Affiche le prénom du citoyen.
    prenomUtilisateur = serializers.CharField(
        source='idUtilisateur.first_name',
        read_only=True
    )

    # Affiche le nom du citoyen.
    nomUtilisateur = serializers.CharField(
        source='idUtilisateur.last_name',
        read_only=True
    )

    # Affiche le téléphone du citoyen.
    telephoneUtilisateur = serializers.CharField(
        source='idUtilisateur.telephone',
        read_only=True
    )

    # Inclut les infos du collecteur attribué à cette demande.
    # NULL tant qu'aucun collecteur n'a accepté (statut en_attente).
    collecteurAttribue = serializers.SerializerMethodField()

    def get_collecteurAttribue(self, obj):
        """
        Retourne les infos du collecteur qui a accepté la demande.
        NULL si la demande est encore en_attente.
        """
        if not obj.collecteurAttribue:
            return None
        return CollecteurAttribueSerializer(obj.collecteurAttribue).data

    # Inclut le résumé de la collecte liée pour la page suivi.
    # NULL si aucun collecteur n'a encore planifié la collecte.
    collecte = serializers.SerializerMethodField()

    def get_collecte(self, obj):
        """
        Retourne la première collecte liée à cette demande.
        C'est cette collecte qui contient la date planifiée de passage.
        """
        collecte = obj.collectes.select_related(
            'idCollecteur__idUtilisateur'
        ).first()

        if not collecte:
            return None

        return CollecteResumeSuiviSerializer(collecte).data

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
        # Le nom historique reste disponible pour les clients non encore migrés.
        return self.get_poidsTotalKg(obj)

    def get_poidsTotalKg(self, obj):
        return sum((detail.poidsKg for detail in self._details(obj)), Decimal('0'))

    def get_nombreObjets(self, obj):
        details = self._details(obj)
        # Une ancienne demande n'a pas de compteur fiable à agréger.
        if any(detail.nombreObjets is None for detail in details):
            return None
        return sum(detail.nombreObjets for detail in details)

    class Meta:
        model = DemandeCollecte
        fields = [
            'idDemande',
            'idUtilisateur',
            'emailUtilisateur',
            'prenomUtilisateur',
            'nomUtilisateur',
            'telephoneUtilisateur',
            'idTypeDechet',
            'typeDechet',
            'quantite',
            'poidsTotalKg',
            'nombreObjets',
            'details',
            'typeDemande',
            'prixPropose',
            'quartier',
            'latitude',
            'longitude',
            'dateDemande',
            'dateSouhaitee',
            'statut',
            # Collecteur qui a accepté la demande (null si en_attente).
            'collecteurAttribue',
            # Collecte planifiée liée (pour la page suivi citoyen).
            'collecte',
        ]
        read_only_fields = [
            'idDemande',
            'idUtilisateur',
            'emailUtilisateur',
            'prenomUtilisateur',
            'nomUtilisateur',
            'telephoneUtilisateur',
            'typeDechet',
            'dateDemande',
            'collecteurAttribue',
            'collecte',
        ]


class LigneDemandeCollecteCreationSerializer(serializers.Serializer):
    """Valide le nombre d'objets sélectionné et le poids mesuré."""

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
    # Compatibilité temporaire avec les clients qui envoyaient le poids comme quantité.
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
        # Les anciens clients n'ayant pas de compteur engagent le stock disponible.
        attrs['nombreObjets'] = attrs.get('nombreObjets') or panier.nombreDisponible
        if attrs['nombreObjets'] <= 0:
            raise serializers.ValidationError({
                'nombreObjets': 'Aucun objet disponible dans ce panier.'
            })
        return attrs


class DemandeCollecteCreationSerializer(serializers.Serializer):
    """
    Crée une demande contenant une ou plusieurs lignes de panier.
    L'ancien format mono-catégorie reste accepté pendant la transition Angular.
    """

    details = LigneDemandeCollecteCreationSerializer(
        many=True,
        required=False,
        min_length=1,
    )

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

    # Coordonnées GPS envoyées automatiquement par le navigateur Angular.
    # required=False : si l'utilisateur refuse la géolocalisation,
    # la demande peut quand même être soumise.
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    typeDemande = serializers.ChoiceField(
        choices=DemandeCollecte.TYPE_DEMANDE_CHOICES,
        required=False,
    )
    prixPropose = serializers.FloatField(required=False, allow_null=True)
    quartier = serializers.CharField(required=False, allow_blank=True)
    dateSouhaitee = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        lignes = attrs.get('details')
        type_dechet = attrs.get('idTypeDechet')
        quantite = attrs.get('quantite')
        if lignes is None:
            if type_dechet is None or quantite is None:
                raise serializers.ValidationError(
                    {'details': 'Fournissez les paniers et quantités à faire ramasser.'}
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
        utilisateur = validated_data.pop('idUtilisateur')
        lignes = validated_data.pop('details')
        validated_data.pop('idTypeDechet', None)
        validated_data.pop('quantite', None)
        paniers = reserver_quantites_paniers(utilisateur, lignes)
        demande = DemandeCollecte.objects.create(
            idUtilisateur=utilisateur,
            **validated_data,
        )
        DetailDemandeCollecte.objects.bulk_create([
            DetailDemandeCollecte(
                idDemande=demande,
                idPanier=paniers[ligne['idPanier'].pk],
                poidsKg=ligne['poidsKg'],
                nombreObjets=ligne['nombreObjets'],
            )
            for ligne in lignes
        ])
        return demande


class DemandeCollecteStatutSerializer(serializers.ModelSerializer):
    """
    Serializer dédié à la mise à jour du statut d'une demande.
    Utilisé par les collecteurs pour accepter une demande
    et par les admins pour changer le statut.
    """

    class Meta:
        model = DemandeCollecte
        fields = ['statut']
