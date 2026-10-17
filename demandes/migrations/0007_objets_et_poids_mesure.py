"""Conserve le poids des demandes historiques et ajoute le compte d'objets."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('demandes', '0006_detaildemandecollecte'),
        ('dechets', '0006_compter_objets'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='detaildemandecollecte',
            name='detail_demande_quantite_positive',
        ),
        migrations.RenameField(
            model_name='detaildemandecollecte',
            old_name='quantite',
            new_name='poidsKg',
        ),
        migrations.AddField(
            model_name='detaildemandecollecte',
            name='nombreObjets',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='detaildemandecollecte',
            constraint=models.CheckConstraint(
                condition=models.Q(('poidsKg__gt', 0)),
                name='detail_demande_poids_positif',
            ),
        ),
        migrations.AddConstraint(
            model_name='detaildemandecollecte',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(('nombreObjets__isnull', True))
                    | models.Q(('nombreObjets__gt', 0))
                ),
                name='detail_demande_objets_positif',
            ),
        ),
    ]
