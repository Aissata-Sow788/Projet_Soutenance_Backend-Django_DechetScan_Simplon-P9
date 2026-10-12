"""Conserve le poids historique des ventes et ajoute le compte d'objets."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0003_detailventedechet'),
        ('dechets', '0006_compter_objets'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='detailventedechet',
            name='detail_vente_quantite_positive',
        ),
        migrations.RenameField(
            model_name='detailventedechet',
            old_name='quantite',
            new_name='poidsKg',
        ),
        migrations.AddField(
            model_name='detailventedechet',
            name='nombreObjets',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='detailventedechet',
            constraint=models.CheckConstraint(
                condition=models.Q(('poidsKg__gt', 0)),
                name='detail_vente_poids_positif',
            ),
        ),
        migrations.AddConstraint(
            model_name='detailventedechet',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(('nombreObjets__isnull', True))
                    | models.Q(('nombreObjets__gt', 0))
                ),
                name='detail_vente_objets_positif',
            ),
        ),
    ]
