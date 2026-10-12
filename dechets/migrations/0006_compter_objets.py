"""Sépare le compte d'objets des anciennes valeurs déclarées en kilogrammes."""

from django.db import migrations, models


def normaliser_unite_paniers(apps, schema_editor):
    """Les paniers actifs deviennent des comptes d'objets, sans conversion des kg."""
    PanierDechet = apps.get_model('dechets', 'PanierDechet')
    PanierDechet.objects.using(schema_editor.connection.alias).update(unite='objet')


class Migration(migrations.Migration):

    dependencies = [
        ('dechets', '0005_panierdechet'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='panierdechet',
            name='panier_quantite_non_negative',
        ),
        migrations.RenameField(
            model_name='panierdechet',
            old_name='quantiteDisponible',
            new_name='quantiteHistoriqueKg',
        ),
        migrations.AlterField(
            model_name='panierdechet',
            name='quantiteHistoriqueKg',
            field=models.DecimalField(
                decimal_places=3,
                default=0,
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name='panierdechet',
            name='nombreDisponible',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='panierdechet',
            name='unite',
            field=models.CharField(default='objet', max_length=20),
        ),
        migrations.RunPython(normaliser_unite_paniers, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='panierdechet',
            constraint=models.CheckConstraint(
                condition=models.Q(('nombreDisponible__gte', 0)),
                name='panier_nombre_non_negative',
            ),
        ),
    ]
