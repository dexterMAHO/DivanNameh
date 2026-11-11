from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('accounts', '0002_email_access')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='action_password',
            field=models.CharField(blank=True, max_length=128),
        ),
    ]
