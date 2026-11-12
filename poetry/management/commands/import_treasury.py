import gzip
import hashlib
import json
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from poetry.models import TreasuryBook, TreasuryEntry
from poetry.services.treasury_metadata import metadata
from poetry.treasury_forms import is_line_poem
from scripts.export_ganjoor import EPUB_ROOT, PUBLISHABLE_EDITIONS, source_url


def publishes_text(record):
    """The dataset records the rights decision made when it was exported."""
    if 'publishes_text' in record:
        return bool(record['publishes_text']) and bool(record['edition_note'])
    return record['slug'] in PUBLISHABLE_EDITIONS


def prepare_entries(record):
    entries = record['entries']
    if entries is None:
        return []
    groups = defaultdict(list)
    depths = {}
    for position, entry in enumerate(entries):
        key = entry['key']
        parent = entry['parent']
        if key in depths or (parent is not None and parent not in depths):
            raise ValueError(f'Invalid parent or duplicate entry: {key}')
        if entry['position'] != position or entry['kind'] not in ('section', 'work'):
            raise ValueError(f'Invalid navigation order or kind: {key}')
        if entry['source_url'] and source_url(entry['source_url']) != entry['source_url']:
            raise ValueError(f'Invalid source URL: {key}')
        if entry['paragraphs'] is not None and not publishes_text(record):
            raise ValueError(f'Publication permission not recorded: {key}')
        depth = 0 if parent is None else depths[parent] + 1
        depths[key] = depth
        groups[depth].append(entry)
    return list(groups.items())


TABLE = TreasuryEntry._meta.db_table
COLUMNS = 'id, book_id, parent_id, key, title, position, kind, source_url, paragraphs, search_body, opening_ending, has_text, reading_count'
# Postgres parses one JSON document far faster than it binds a parameter per column,
# and the trip over the wire is what makes a full re-import slow.
BULK_INSERT = f"""
INSERT INTO {TABLE} ({COLUMNS})
SELECT {COLUMNS} FROM json_to_recordset(%s::json)
AS entry(id bigint, book_id bigint, parent_id bigint, key varchar, title text,
         position integer, kind varchar, source_url varchar, paragraphs json,
         search_body text, opening_ending varchar, has_text boolean, reading_count integer)
"""
INSERT_BATCH = 2000


def delete_entries(book):
    """One statement, instead of Django's recursive cascade walk over the self reference."""
    with connection.cursor() as cursor:
        cursor.execute(f'DELETE FROM {TABLE} WHERE book_id = %s', [book.pk])


def insert_entries(book, groups):
    """Write a book's entries, resolving each parent reference before the insert."""
    entries = [entry for _, group in sorted(groups) for entry in group]
    if not entries:
        return
    by_key = {entry['key']: entry for entry in entries}

    def layout(entry):
        sections = []
        parent = by_key.get(entry['parent'])
        while parent:
            sections.append((parent['key'], parent['title']))
            parent = by_key.get(parent['parent'])
        return is_line_poem(book.slug, entry['key'], entry['title'], sections)

    layouts = {entry['key']: bool(entry['paragraphs'] and layout(entry)) for entry in entries}
    if connection.vendor != 'postgresql':
        insert_entries_by_depth(book, groups, layouts)
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT nextval(pg_get_serial_sequence(%s, 'id')) FROM generate_series(1, %s)",
            [TABLE, len(entries)])
        ids = dict(zip((entry['key'] for entry in entries), (row[0] for row in cursor.fetchall())))
        # The self reference is deferred, so children may be written before their parent.
        rows = [{
            'id': ids[entry['key']], 'book_id': book.pk, 'parent_id': ids.get(entry['parent']),
            'key': entry['key'], 'title': entry['title'], 'position': entry['position'],
            'kind': entry['kind'], 'source_url': entry['source_url'], 'paragraphs': entry['paragraphs'],
            **metadata(entry['paragraphs'], line_layout=layouts[entry['key']]),
        } for entry in entries]
        for start in range(0, len(rows), INSERT_BATCH):
            batch = json.dumps(rows[start:start + INSERT_BATCH], ensure_ascii=False)
            cursor.execute(BULK_INSERT, [batch])


def insert_entries_by_depth(book, groups, layouts):
    """SQLite and friends: let the ORM assign the keys, one generation at a time."""
    ids = {}
    for _, entries in sorted(groups):
        rows = [TreasuryEntry(
            book_id=book.pk, parent_id=ids.get(entry['parent']),
            key=entry['key'], title=entry['title'], position=entry['position'],
            kind=entry['kind'], source_url=entry['source_url'], paragraphs=entry['paragraphs'],
        ) for entry in entries]
        for row in rows:
            row._reading_layout = layouts[row.key]
        TreasuryEntry.objects.bulk_create(rows, batch_size=INSERT_BATCH)
        ids.update((row.key, row.pk) for row in rows)


@transaction.atomic
def import_book(record, digest):
    slug = record['slug']
    if record['source_url'] != f'{EPUB_ROOT}{slug}.epub':
        raise ValueError('Invalid EPUB URL')
    book = TreasuryBook.objects.select_for_update().filter(slug=slug).first()
    if book and (book.dataset_digest == digest or (book.has_contents and record['entries'] is None)):
        return False
    groups = prepare_entries(record)
    kinds = Counter(entry['kind'] for _, entries in groups for entry in entries)
    fields = {
        'author': record['author'],
        'source_url': record['source_url'],
        'has_contents': record['entries'] is not None,
        'publishes_text': bool(groups and publishes_text(record)),
        'edition_note': record.get('edition_note') or PUBLISHABLE_EDITIONS.get(slug, ''),
        'dataset_digest': digest,
        'section_count': kinds['section'],
        'work_count': kinds['work'],
    }
    if book is None:
        book = TreasuryBook.objects.create(slug=slug, **fields)
    else:
        delete_entries(book)
        for name, value in fields.items():
            setattr(book, name, value)
        book.save(update_fields=fields)
    insert_entries(book, groups)
    return True


class Command(BaseCommand):
    help = 'Import a Ganjoor JSONL.gz dataset into the shared treasury.'

    def add_arguments(self, parser):
        parser.add_argument('dataset')

    def handle(self, *args, **options):
        changed = 0
        try:
            with gzip.open(options['dataset'], 'rb') as dataset:
                for line_number, line in enumerate(dataset, 1):
                    try:
                        record = json.loads(line)
                        changed += import_book(record, hashlib.sha256(line).hexdigest())
                    except (KeyError, TypeError, ValueError) as error:
                        raise CommandError(f'Dataset line {line_number}: {error}') from error
                    if line_number % 25 == 0:
                        self.stdout.write(f'Processed {line_number} books')
        except OSError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f'Updated {changed} books.'))
