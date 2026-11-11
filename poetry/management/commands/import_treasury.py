import gzip
import hashlib
import json
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from poetry.models import TreasuryBook, TreasuryEntry
from scripts.export_ganjoor import EPUB_ROOT, PUBLISHABLE_EDITIONS, source_url


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
        if entry['paragraphs'] is not None and record['slug'] not in PUBLISHABLE_EDITIONS:
            raise ValueError(f'Publication permission not recorded: {key}')
        depth = 0 if parent is None else depths[parent] + 1
        depths[key] = depth
        groups[depth].append(entry)
    return list(groups.items())


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
        'publishes_text': bool(groups and slug in PUBLISHABLE_EDITIONS),
        'edition_note': PUBLISHABLE_EDITIONS.get(slug, ''),
        'dataset_digest': digest,
        'section_count': kinds['section'],
        'work_count': kinds['work'],
    }
    if book is None:
        book = TreasuryBook.objects.create(slug=slug, **fields)
    else:
        book.entries.all().delete()
        for name, value in fields.items():
            setattr(book, name, value)
        book.save(update_fields=fields)
    ids = {}
    for _, entries in sorted(groups):
        rows = [TreasuryEntry(
            book_id=book.pk, parent_id=ids.get(entry['parent']),
            key=entry['key'], title=entry['title'], position=entry['position'],
            kind=entry['kind'], source_url=entry['source_url'], paragraphs=entry['paragraphs'],
        ) for entry in entries]
        TreasuryEntry.objects.bulk_create(rows, batch_size=750)
        ids.update((row.key, row.pk) for row in rows)
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
