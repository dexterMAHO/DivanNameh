from django.db import migrations


def allow_legacy_motion_default(apps, schema_editor):
    """Keep the orphaned accessibility column without blocking new accounts.

    Some deployed databases applied 0011_user_reduce_motion from an earlier
    branch. That migration is absent from the current model state, so INSERTs
    omit reduce_motion while its old NOT NULL constraint remains in PostgreSQL.
    A database default preserves existing preferences and accepts new readers.
    """
    connection = schema_editor.connection
    if connection.vendor != 'postgresql':
        return
    user = apps.get_model('accounts', 'User')
    table = user._meta.db_table
    with connection.cursor() as cursor:
        columns = connection.introspection.get_table_description(cursor, table)
        if 'reduce_motion' not in {column.name for column in columns}:
            return
        cursor.execute('SET LOCAL lock_timeout = \'5s\'')
        cursor.execute(
            f'ALTER TABLE {schema_editor.quote_name(table)} '
            f'ALTER COLUMN {schema_editor.quote_name("reduce_motion")} SET DEFAULT FALSE'
        )


class Migration(migrations.Migration):
    dependencies = [('accounts', '0011_alter_user_palette')]
    operations = [migrations.RunPython(allow_legacy_motion_default, migrations.RunPython.noop)]
