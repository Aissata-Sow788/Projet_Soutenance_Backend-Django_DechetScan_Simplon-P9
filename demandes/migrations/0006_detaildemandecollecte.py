"""Convertit les anciennes demandes mono-catégorie en lignes de détail."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrer_demandes_existantes(apps, schema_editor):
    """Préserve les anciennes quantités sans créer de stock historique fictif."""
    DemandeCollecte = apps.get_model('demandes', 'DemandeCollecte')
    DetailDemandeCollecte = apps.get_model('demandes', 'DetailDemandeCollecte')
    PanierDechet = apps.get_model('dechets', 'PanierDechet')
    database = schema_editor.connection.alias

    for demande in DemandeCollecte.objects.using(database).iterator():
        if (
            demande.idUtilisateur_id is None
            or demande.idTypeDechet_id is None
            or demande.quantite is None
            or demande.quantite <= 0
        ):
            continue
        panier, _ = PanierDechet.objects.using(database).get_or_create(
            idUtilisateur_id=demande.idUtilisateur_id,
            idTypeDechet_id=demande.idTypeDechet_id,
            defaults={'quantiteDisponible': 0, 'unite': 'kg'},
        )
        DetailDemandeCollecte.objects.using(database).create(
            idDemande_id=demande.pk,
            idPanier_id=panier.pk,
            quantite=demande.quantite,
        )
    DemandeCollecte.objects.using(database).update(stockRestitue=True)


class Migration(migrations.Migration):

    dependencies = [
        ('dechets', '0005_panierdechet'),
        ('demandes', '0005_demandecollecte_refuseurs'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandecollecte',
            name='stockRestitue',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='DetailDemandeCollecte',
            fields=[
                ('idDetail', models.AutoField(primary_key=True, serialize=False)),
                ('quantite', models.DecimalField(decimal_places=3, max_digits=12)),
                ('idDemande', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='details',
                    to='demandes.demandecollecte',
                )),
                ('idPanier', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='detailsDemandes',
                    to='dechets.panierdechet',
                )),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(
                        fields=('idDemande', 'idPanier'),
                        name='unique_panier_par_demande',
                    ),
                    models.CheckConstraint(
                        condition=models.Q(('quantite__gt', 0)),
                        name='detail_demande_quantite_positive',
                    ),
                ],
            },
        ),
        migrations.RunPython(migrer_demandes_existantes, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='demandecollecte',
            name='idTypeDechet',
        ),
        migrations.RemoveField(
            model_name='demandecollecte',
            name='quantite',
        ),
    ]
