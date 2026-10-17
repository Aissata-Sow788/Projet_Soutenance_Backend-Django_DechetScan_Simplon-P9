from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('collecteurs', '0001_initial'),
        ('dechets', '0007_restaurer_anciens_comptes_panier'),
    ]

    operations = [
        migrations.AddField(
            model_name='prixdechet',
            name='idCollecteur',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tarifs',
                to='collecteurs.collecteur',
            ),
        ),
    ]
