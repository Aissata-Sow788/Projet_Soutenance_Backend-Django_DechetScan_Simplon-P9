"""Crée un panier unique par citoyen et catégorie de déchet."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dechets', '0004_prixdechet'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PanierDechet',
            fields=[
                ('idPanier', models.AutoField(primary_key=True, serialize=False)),
                ('quantiteDisponible', models.DecimalField(decimal_places=3, max_digits=12)),
                ('unite', models.CharField(default='kg', max_length=20)),
                ('dateMiseAJour', models.DateTimeField(auto_now=True)),
                ('idTypeDechet', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='paniers',
                    to='dechets.typedechet',
                )),
                ('idUtilisateur', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='paniersDechets',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(
                        fields=('idUtilisateur', 'idTypeDechet'),
                        name='unique_panier_citoyen_type_dechet',
                    ),
                    models.CheckConstraint(
                        condition=models.Q(('quantiteDisponible__gte', 0)),
                        name='panier_quantite_non_negative',
                    ),
                ],
            },
        ),
    ]
