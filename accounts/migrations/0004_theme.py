from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('accounts', '0003_action_password')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='theme',
            field=models.CharField(choices=[('auto', 'مطابق دستگاه'), ('light', 'روشن'), ('dark', 'تاریک')], default='auto', max_length=5),
        ),
    ]
