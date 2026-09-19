from django.db import migrations


def creer_referentiel(apps, schema_editor):
    TypeDechet = apps.get_model('dechets', 'TypeDechet')
    ConseilTri = apps.get_model('dechets', 'ConseilTri')

    referentiel = [
        (
            "Plastique",
            "Bouteilles, emballages et objets en plastique.",
            "Déposer les déchets plastiques propres et vides dans un point de collecte adapté."
        ),
        (
            "Papier",
            "Feuilles, journaux, magazines et autres papiers.",
            "Garder les papiers propres et secs puis les déposer dans un point de collecte adapté."
        ),
        (
            "Carton",
            "Boîtes, emballages et cartons.",
            "Aplatir les cartons et les garder au sec avant leur dépôt."
        ),
        (
            "Verre",
            "Bouteilles, bocaux et autres emballages en verre.",
            "Retirer les bouchons et déposer le verre sans le casser."
        ),
        (
            "Métal",
            "Canettes, boîtes métalliques et autres objets en métal.",
            "Rincer les contenants métalliques et les déposer dans une filière de collecte adaptée."
        ),
        (
            "Textile",
            "Vêtements, tissus et autres articles textiles.",
            "Donner ou déposer les textiles encore utilisables dans un point de collecte approprié."
        ),
        (
            "Bois",
            "Objets et déchets constitués principalement de bois.",
            "Séparer le bois des autres déchets et le déposer dans une filière de valorisation adaptée."
        ),
        (
            "Déchet organique",
            "Déchets provenant principalement de matières biodégradables.",
            "Déposer les déchets organiques dans une filière de compostage ou de valorisation adaptée."
        ),
        (
            "Déchet électronique",
            "Appareils électriques et électroniques en fin de vie.",
            "Ne pas jeter avec les ordures classiques et déposer dans un point de collecte spécialisé."
        ),
        (
            "Pile et batterie",
            "Piles, batteries et accumulateurs usagés.",
            "Ne jamais jeter avec les ordures classiques. Déposer dans un point de collecte spécialisé."
        ),
        (
            "Déchet médical",
            "Déchets provenant notamment de soins ou de matériel médical.",
            "Ne pas mélanger avec les déchets ménagers et utiliser une filière spécialisée."
        ),
        (
            "Déchet dangereux",
            "Déchets pouvant présenter un risque pour la santé ou l'environnement.",
            "Ne pas jeter avec les ordures ménagères. Utiliser une filière de collecte spécialisée."
        ),
        (
            "Huile usagée",
            "Huiles alimentaires ou autres huiles usagées.",
            "Ne pas verser dans l'évier ou dans la nature. Stocker séparément et déposer dans une filière adaptée."
        ),
        (
            "Déchet de construction",
            "Débris et matériaux issus de travaux de construction ou de rénovation.",
            "Séparer les matériaux et les déposer dans une filière adaptée aux déchets de construction."
        ),
        (
            "Déchet vert",
            "Feuilles, branches, herbes et autres déchets issus des végétaux.",
            "Valoriser par compostage ou déposer dans une filière spécialisée pour déchets verts."
        ),
        (
            "Caoutchouc",
            "Objets et matériaux principalement constitués de caoutchouc.",
            "Séparer des autres déchets et rechercher une filière de valorisation adaptée."
        ),
        (
            "Cuir",
            "Objets et articles constitués principalement de cuir.",
            "Donner ou réutiliser les articles encore utilisables et orienter les autres vers une filière adaptée."
        ),
        (
            "Déchet composite",
            "Objets constitués de plusieurs matériaux difficiles à séparer.",
            "Ne pas mélanger avec une filière spécifique si les matériaux ne peuvent pas être séparés."
        ),
        (
            "Déchet non recyclable",
            "Déchets qui ne peuvent pas être orientés vers une filière de recyclage identifiée.",
            "Déposer dans la filière des déchets résiduels prévue par le système local de collecte."
        ),
        (
            "Inconnu",
            "Déchet que le système n'a pas pu identifier avec suffisamment de certitude.",
            "Ne pas appliquer automatiquement une consigne. Vérifier l'identification avant de choisir une filière de tri."
        ),
    ]

    for nom, description, consigne in referentiel:

        # Crée le type s'il n'existe pas déjà.
        type_dechet, _ = TypeDechet.objects.get_or_create(
            nom=nom,
            defaults={
                "description": description
            }
        )

        # Met à jour la description si le type existait déjà.
        if type_dechet.description != description:
            type_dechet.description = description
            type_dechet.save(update_fields=["description"])

        # Crée le conseil associé au type.
        ConseilTri.objects.update_or_create(
            idTypeDechet=type_dechet,
            defaults={
                "consigne": consigne
            }
        )


def supprimer_referentiel(apps, schema_editor):
    # Cette fonction permet d'annuler la migration.
    TypeDechet = apps.get_model('dechets', 'TypeDechet')

    noms = [
        "Plastique",
        "Papier",
        "Carton",
        "Verre",
        "Métal",
        "Textile",
        "Bois",
        "Déchet organique",
        "Déchet électronique",
        "Pile et batterie",
        "Déchet médical",
        "Déchet dangereux",
        "Huile usagée",
        "Déchet de construction",
        "Déchet vert",
        "Caoutchouc",
        "Cuir",
        "Déchet composite",
        "Déchet non recyclable",
        "Inconnu",
    ]

    TypeDechet.objects.filter(nom__in=noms).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dechets', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            creer_referentiel,
            supprimer_referentiel
        ),
    ]
