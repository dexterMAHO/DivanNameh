from django.db import migrations


def backfill(apps, schema_editor):
    from poetry.services.treasury_metadata import metadata
    from poetry.treasury_forms import is_line_poem

    entry = apps.get_model('poetry', 'TreasuryEntry')
    entries = entry.objects.using(schema_editor.connection.alias)
    sections = {
        pk: (parent, key, title)
        for pk, parent, key, title in entries.filter(kind='section').values_list('pk', 'parent_id', 'key', 'title')
    }
    last_pk = 0
    while batch := list(entries.filter(pk__gt=last_pk, paragraphs__isnull=False).order_by('pk').select_related('book').only(
        'pk', 'paragraphs', 'book__slug', 'key', 'title', 'parent',
    )[:250]):
        for row in batch:
            parents = []
            parent = row.parent_id
            while parent in sections:
                parent, key, title = sections[parent]
                parents.append((key, title))
            line_layout = is_line_poem(row.book.slug, row.key, row.title, parents)
            for name, value in metadata(row.paragraphs, line_layout=line_layout).items():
                setattr(row, name, value)
        entries.bulk_update(batch, ['search_body', 'opening_ending', 'has_text', 'reading_count'])
        last_pk = batch[-1].pk


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('poetry', '0009_poem_treasury_book_slug_poem_treasury_edition_and_more')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
