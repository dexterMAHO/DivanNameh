"""Restore an explicitly approved library export only into an empty target."""
import json
from pathlib import Path

from django.apps import apps
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction

LIBRARY_MODELS = {
    'accounts.user', 'auth.group', 'poetry.poem', 'poetry.verse', 'poetry.tag',
    'poetry.favoriteverse', 'memorization.memorizationitem', 'memorization.reviewlog',
}


class Command(BaseCommand):
    help = 'Import a library export into an empty database; never merge or overwrite existing records.'

    def add_arguments(self, parser):
        parser.add_argument('fixture', type=Path)
        parser.add_argument('--confirm-empty-target', action='store_true')

    def handle(self, *args, **options):
        if not options['confirm_empty_target']:
            raise CommandError('Inspect the target first, then pass --confirm-empty-target to authorize import.')
        path = options['fixture']
        if path.suffix != '.json' or not path.is_file():
            raise CommandError('Provide an existing .json library export.')
        try:
            records = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError):
            raise CommandError('The export is not a readable JSON fixture.') from None
        if not isinstance(records, list) or not records:
            raise CommandError('The export must be a nonempty JSON fixture list.')
        if any(not isinstance(row, dict) or row.get('model', '').lower() not in LIBRARY_MODELS for row in records):
            raise CommandError('Export contains unsupported models. Use the documented library-only dumpdata command.')
        with transaction.atomic():
            if any(apps.get_model(label).objects.exists() for label in LIBRARY_MODELS):
                raise CommandError('Target is not empty. Import refused; existing data was not modified.')
            # loaddata validates references and resets sequences. Its transaction is nested here.
            call_command('loaddata', str(path.resolve()), verbosity=0)
        self.stdout.write(self.style.SUCCESS('Library imported into the empty target.'))
