from importlib import import_module
from django.db import migrations


def refresh(apps, schema_editor):
    import_module('poetry.migrations.0010_backfill_treasury_metadata').backfill(apps, schema_editor)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('poetry', '0017_operationrequest')]
    operations = [migrations.RunPython(refresh, migrations.RunPython.noop)]
