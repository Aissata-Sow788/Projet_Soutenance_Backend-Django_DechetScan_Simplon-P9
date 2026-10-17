"""Restaure les anciens comptes de déchets confirmés par la citoyenne."""

from django.db import migrations


def restaurer_comptes_confirmes(apps, schema_editor):
    """Recopie les valeurs historiques entières dans le compteur d'objets."""
    PanierDechet = apps.get_model('dechets', 'PanierDechet')
    base = PanierDechet.objects.using(schema_editor.connection.alias)

    # La citoyenne a confirmé que les anciennes quantités étiquetées « kg »
    # correspondaient en réalité aux nombres d'objets présents dans ses paniers.
    paniers = list(base.filter(quantiteHistoriqueKg__gt=0).iterator())
    fractionnaires = [
        (panier.pk, panier.quantiteHistoriqueKg)
        for panier in paniers
        if panier.quantiteHistoriqueKg != panier.quantiteHistoriqueKg.to_integral_value()
    ]
    if fractionnaires:
        raise RuntimeError(
            'Restauration du panier annulée : certaines anciennes quantités '
            'ne sont pas des nombres entiers et ne peuvent pas devenir des objets.'
        )

    for panier in paniers:
        # Un compte déjà modifié depuis la migration précédente est préservé.
        if panier.nombreDisponible == 0:
            base.filter(pk=panier.pk).update(
                nombreDisponible=int(panier.quantiteHistoriqueKg)
            )


class Migration(migrations.Migration):

    dependencies = [
        ('dechets', '0006_compter_objets'),
    ]

    operations = [
        migrations.RunPython(
            restaurer_comptes_confirmes,
            migrations.RunPython.noop,
        ),
    ]
