from django.db import migrations


def nettoyer_referentiel(apps, schema_editor):
    # Récupère les modèles historiques utilisés par la migration.
    TypeDechet = apps.get_model("dechets", "TypeDechet")
    ConseilTri = apps.get_model("dechets", "ConseilTri")
    AnalyseIA = apps.get_model("scans", "AnalyseIA")

    # Correspondance entre les anciennes catégories
    # et les nouvelles catégories officielles.
    correspondances = {
        "Organique": "Déchet organique",
        "Électronique": "Déchet électronique",
        "Papier-carton": "Carton",
    }

    for ancien_nom, nouveau_nom in correspondances.items():

        try:
            ancien_type = TypeDechet.objects.get(nom=ancien_nom)
            nouveau_type = TypeDechet.objects.get(nom=nouveau_nom)
        except TypeDechet.DoesNotExist:
            continue

        # Les anciennes analyses sont rattachées
        # à la nouvelle catégorie correspondante.
        AnalyseIA.objects.filter(
            idTypeDechet=ancien_type
        ).update(
            idTypeDechet=nouveau_type
        )

        # Le conseil de tri de l'ancienne catégorie
        # devient inutile puisque la nouvelle catégorie
        # possède déjà son propre conseil.
        ConseilTri.objects.filter(
            idTypeDechet=ancien_type
        ).delete()

        # Supprime l'ancienne catégorie.
        ancien_type.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("dechets", "0002_populate_referentiel_dechets"),
        ("scans", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            nettoyer_referentiel,
            migrations.RunPython.noop,
        ),
    ]
