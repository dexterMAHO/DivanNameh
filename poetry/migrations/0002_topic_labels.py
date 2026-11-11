from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('poetry', '0001_initial')]

    operations = [
        migrations.AlterField(
            model_name='poem',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='poems', to='poetry.tag', verbose_name='موضوع\u200cها'),
        ),
    ]
