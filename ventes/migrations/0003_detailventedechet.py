"""Convertit les ventes existantes en lignes et conserve leur prix historique."""

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


def migrer_ventes_existantes(apps, schema_editor):
    """Reconstitue les lignes sans créditer comme stock un déchet déjà vendu."""
    VenteDechet = apps.get_model('ventes', 'VenteDechet')
    DetailVenteDechet = apps.get_model('ventes', 'DetailVenteDechet')
    PanierDechet = apps.get_model('dechets', 'PanierDechet')
    database = schema_editor.connection.alias

    for vente in VenteDechet.objects.using(database).iterator():
        if (
            vente.idUtilisateur_id is None
            or vente.idTypeDechet_id is None
            or vente.quantite is None
            or vente.quantite <= 0
        ):
            continue
        panier, _ = PanierDechet.objects.using(database).get_or_create(
            idUtilisateur_id=vente.idUtilisateur_id,
            idTypeDechet_id=vente.idTypeDechet_id,
            defaults={
                'quantiteHistoriqueKg': Decimal('0'),
                'nombreDisponible': 0,
                'unite': 'objet',
}, )
        prix_unitaire = (
            Decimal(str(vente.prixPaye)) / Decimal(str(vente.quantite))
            if vente.quantite
            else Decimal('0')
        )
        DetailVenteDechet.objects.using(database).create(
            idVente_id=vente.pk,
            idPanier_id=panier.pk,
            quantite=vente.quantite,
            prixParKg=prix_unitaire.quantize(Decimal('0.01')),
        )
    VenteDechet.objects.using(database).update(stockRestitue=True)


class Migration(migrations.Migration):

    dependencies = [
        ('dechets', '0008_tarifs_par_collecteur'),
        ('ventes', '0002_ventedechet_tokenpaydunya'),
    ]

    operations = [
        migrations.AddField(
            model_name='ventedechet',
            name='stockRestitue',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='DetailVenteDechet',
            fields=[
                ('idDetail', models.AutoField(primary_key=True, serialize=False)),
                ('quantite', models.DecimalField(decimal_places=3, max_digits=12)),
                ('prixParKg', models.DecimalField(decimal_places=2, max_digits=12)),
                ('idPanier', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='detailsVentes',
                    to='dechets.panierdechet',
                )),
                ('idVente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='details',
                    to='ventes.ventedechet',
                )),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(
                        fields=('idVente', 'idPanier'),
                        name='unique_panier_par_vente',
                    ),
                    models.CheckConstraint(
                        condition=models.Q(('quantite__gt', 0)),
                        name='detail_vente_quantite_positive',
                    ),
                    models.CheckConstraint(
                        condition=models.Q(('prixParKg__gte', 0)),
                        name='detail_vente_prix_non_negative',
                    ),
                ],
            },
        ),
        migrations.RunPython(migrer_ventes_existantes, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='ventedechet',
            name='idTypeDechet',
        ),
        migrations.RemoveField(
            model_name='ventedechet',
            name='quantite',
        ),
        migrations.AlterField(
            model_name='ventedechet',
            name='prixPaye',
            field=models.DecimalField(decimal_places=2, max_digits=14),
        ),
    ]
