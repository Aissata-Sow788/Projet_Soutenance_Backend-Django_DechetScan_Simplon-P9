from django.core.management.base import BaseCommand
from dechets.models import TypeDechet, ConseilTri


class Command(BaseCommand):
    help = "Remplit la table TypeDechet avec les types de base et leurs conseils"

    def handle(self, *args, **kwargs):
        # Liste fixe des types de base : (nom, description, consigne de tri)
        donnees = [
            ('Plastique', 'Bouteilles, emballages plastiques', 'Rincez et compressez avant de déposer dans le bac dédié au plastique.'),
            ('Verre', 'Bouteilles, bocaux en verre', 'Retirez le bouchon et déposez sans casser le verre.'),
            ('Métal', 'Canettes, boîtes de conserve', 'Rincez la canette et écrasez-la légèrement.'),
            ('Papier-carton', 'Journaux, cartons, emballages papier', 'Aplatissez les cartons et gardez-les au sec.'),
            ('Organique', 'Déchets alimentaires et végétaux', 'Déposez dans le compost ou le bac organique le plus proche.'),
            ('Électronique', 'Piles, appareils électroniques', 'Ne jetez jamais avec les ordures classiques.'),
        ]

        for nom, description, consigne in donnees:
            # get_or_create évite les doublons si le script est relancé plusieurs fois
            type_dechet, cree = TypeDechet.objects.get_or_create(
                nom=nom, defaults={'description': description}
            )
            # Crée le conseil lié à ce type, seulement s'il n'existe pas déjà
            ConseilTri.objects.get_or_create(
                idTypeDechet=type_dechet, defaults={'consigne': consigne}
            )
            # Affiche dans le terminal si c'était une création ou un doublon évité
            if cree:
                self.stdout.write(f"Créé : {nom}")
            else:
                self.stdout.write(f"Déjà existant : {nom}")