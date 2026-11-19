"""Copy the treasury corpus from one database into this one.

The corpus — poets, works, their text, and the editorial picks, topics, sets and
literary links on top of them — is reference data. It is the part of the product
that a demo site needs in order to be worth looking at.

Readers' own data is deliberately not copied. The corpus is cleanly separable:
every foreign key between treasury models points at another treasury model, and
a saved poem links back to its origin through plain slug fields rather than a
foreign key. So a demo can hold the identical corpus beside empty user tables.

    python manage.py clone_treasury --from "postgresql://…/divannameh" --replace

Primary keys are preserved so the editorial links keep pointing at the same
works, which also makes a second run with --replace produce the same database.
"""

import dj_database_url
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, models, transaction

from poetry.models import (
    TreasuryBook, TreasuryEntry, TreasuryPick, TreasurySet, TreasurySetVerse,
    TreasuryTopic, TreasuryVerseLink,
)

SOURCE = 'treasury_source'
# Replacement order is the reverse of creation order, so nothing is orphaned.
CORPUS = (TreasuryBook, TreasuryEntry, TreasuryTopic, TreasuryPick,
          TreasurySet, TreasurySetVerse, TreasuryVerseLink)


def plain(model, using):
    """A queryset without TreasuryEntry's bulk_create override.

    That override recomputes reading metadata for every row, and computing it
    walks each entry's parents one query at a time. The values being copied were
    already computed on the source, so recomputing them here would be both slow
    and pointless.
    """
    return models.QuerySet(model=model, using=using)


class Command(BaseCommand):
    help = 'Copy the treasury corpus from another database into this one.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--from', dest='source_url', required=True,
            help='Database URL to read the corpus from. Opened read-only in practice: '
                 'this command never writes to it.',
        )
        parser.add_argument(
            '--replace', action='store_true',
            help='Delete the corpus already in this database first. Required when '
                 'this database already holds treasury rows.',
        )
        parser.add_argument('--batch-size', type=int, default=200)

    def handle(self, *, source_url, replace, batch_size, **options):
        # A connection added at runtime skips the per-alias defaults Django applies
        # at startup (TIME_ZONE, OPTIONS, health checks …). Start from the live
        # settings of the default connection and replace only where to connect.
        target = connections['default'].settings_dict
        source = {**target, **dj_database_url.parse(source_url, conn_max_age=0)}
        source['TEST'] = {**target.get('TEST', {})}
        connections.databases[SOURCE] = source
        if (source.get('NAME'), source.get('HOST')) == (target.get('NAME'), target.get('HOST')):
            raise CommandError('Source and target are the same database; nothing to copy.')

        existing = {model.__name__: plain(model, 'default').count() for model in CORPUS}
        if any(existing.values()) and not replace:
            raise CommandError(
                'This database already holds a treasury corpus '
                f'({", ".join(f"{k}={v}" for k, v in existing.items() if v)}). '
                'Re-run with --replace to rebuild it.')

        with transaction.atomic(using='default'):
            if replace:
                for model in reversed(CORPUS):
                    removed, _ = plain(model, 'default').delete()
                    if removed:
                        self.stdout.write(f'  removed {removed} {model.__name__}')

            self.copy_books(batch_size)
            self.copy_entries(batch_size)
            self.copy_simple(TreasuryTopic, batch_size)
            self.copy_picks(batch_size)
            self.copy_simple(TreasurySet, batch_size)
            self.copy_simple(TreasurySetVerse, batch_size)
            self.copy_simple(TreasuryVerseLink, batch_size)

        totals = ', '.join(f'{model.__name__}={plain(model, "default").count()}' for model in CORPUS)
        self.stdout.write(self.style.SUCCESS(f'Corpus copied. {totals}'))
        self.stdout.write('Reader accounts, saved poems, shahbeyts and review cards were not copied.')

    def copy_simple(self, model, batch_size):
        rows = plain(model, SOURCE).order_by('pk').iterator(chunk_size=batch_size)
        written = plain(model, 'default').bulk_create(list(rows), batch_size=batch_size)
        self.stdout.write(f'  {model.__name__}: {len(written)}')

    def copy_books(self, batch_size):
        self.copy_simple(TreasuryBook, batch_size)

    def copy_entries(self, batch_size):
        """Insert parents before children so the self-referencing key resolves."""
        parents = dict(plain(TreasuryEntry, SOURCE).values_list('pk', 'parent_id'))
        depth, pending, total = {}, set(parents), 0
        while pending:
            ready = [pk for pk in pending if parents[pk] is None or parents[pk] in depth]
            if not ready:
                raise CommandError('The source entry tree contains a cycle.')
            for pk in ready:
                depth[pk] = 0 if parents[pk] is None else depth[parents[pk]] + 1
            pending -= set(ready)
        levels = {}
        for pk, value in depth.items():
            levels.setdefault(value, []).append(pk)
        for value in sorted(levels):
            ids = levels[value]
            for start in range(0, len(ids), batch_size):
                chunk = ids[start:start + batch_size]
                rows = list(plain(TreasuryEntry, SOURCE).filter(pk__in=chunk))
                plain(TreasuryEntry, 'default').bulk_create(rows, batch_size=batch_size)
                total += len(rows)
        self.stdout.write(f'  TreasuryEntry: {total}')

    def copy_picks(self, batch_size):
        picks = list(plain(TreasuryPick, SOURCE).order_by('pk'))
        plain(TreasuryPick, 'default').bulk_create(picks, batch_size=batch_size)
        through = TreasuryPick.topics.through
        links = list(plain(through, SOURCE).order_by('pk'))
        plain(through, 'default').bulk_create(links, batch_size=batch_size)
        self.stdout.write(f'  TreasuryPick: {len(picks)} (+{len(links)} topic links)')
