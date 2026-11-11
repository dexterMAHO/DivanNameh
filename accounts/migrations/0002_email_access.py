from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('accounts', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='LoginChallenge',
            fields=[
                ('email', models.EmailField(max_length=254, primary_key=True, serialize=False)),
                ('token_hash', models.CharField(max_length=64, unique=True)),
                ('issued_at', models.DateTimeField()),
            ],
        ),
        migrations.AddField(
            model_name='user',
            name='login_email',
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True, verbose_name='ایمیل ورود'),
        ),
    ]
