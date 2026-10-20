"""Convertit les anciennes demandes mono-catégorie en lignes de détail."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrer_demandes_existantes(apps, schema_editor):
    """Transfère les anciennes demandes vers leurs lignes de détail."""

    # Récupère les modèles correspondant à l'état de la migration.
    DemandeCollecte = apps.get_model(
        'demandes', 'DemandeCollecte'
    )
    DetailDemandeCollecte = apps.get_model(
        'demandes', 'DetailDemandeCollecte'
    )
    PanierDechet = apps.get_model(
        'dechets', 'PanierDechet'
    )

    # Utilise la même base de données que la migration.
    database = schema_editor.connection.alias

    # Parcourt les anciennes demandes.
    for demande in DemandeCollecte.objects.using(database).iterator():

        # Ignore les demandes sans utilisateur, catégorie ou quantité valide.
        if (
            demande.idUtilisateur_id is None
            or demande.idTypeDechet_id is None
            or demande.quantite is None
            or demande.quantite <= 0
        ):
            continue

        # Crée ou récupère le panier du citoyen pour cette catégorie.
        # Les anciennes quantités ne sont pas ajoutées au stock disponible.
        panier, _ = PanierDechet.objects.using(database).get_or_create(
            idUtilisateur_id=demande.idUtilisateur_id,
            idTypeDechet_id=demande.idTypeDechet_id,
            defaults={
                'quantiteHistoriqueKg': 0,
                'nombreDisponible': 0,
                'unite': 'objet',
            },
        )

        # Enregistre la quantité historique dans le détail de la demande.
        DetailDemandeCollecte.objects.using(database).create(
            idDemande_id=demande.pk,
            idPanier_id=panier.pk,
            quantite=demande.quantite,
        )

    # Marque les anciennes demandes comme déjà traitées pour le stock.
    DemandeCollecte.objects.using(database).update(
        stockRestitue=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ('dechets', '0005_panierdechet'),
        ('demandes', '0005_demandecollecte_refuseurs'),
    ]

    operations = [
    # La colonne existe déjà dans MySQL.
    # On met à jour l'état Django sans recréer la colonne.
    migrations.SeparateDatabaseAndState(
        database_operations=[],
        state_operations=[
            migrations.AddField(
                model_name='demandecollecte',
                name='stockRestitue',
                field=models.BooleanField(default=False),
            ),
        ],
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
