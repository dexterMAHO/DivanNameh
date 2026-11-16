import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from poetry.models import TreasuryBook, TreasuryEntry, TreasuryPick, TreasurySet, TreasurySetVerse, TreasuryTopic, TreasuryVerseLink


class Command(BaseCommand):
    help = 'Populate the starter collection without overwriting editorial decisions or source texts.'

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(__file__).resolve().parents[2] / 'data' / 'treasury_starter.json'
        topics = dict([
            ('road', 'راه و سفر'), ('separation', 'دوری و بازگشت'), ('love', 'عشق'), ('hope', 'امید'),
        ])
        topics = {slug: TreasuryTopic.objects.get_or_create(slug=slug, defaults={'title': title})[0]
                  for slug, title in topics.items()}
        assignments = {
            1: ('road', 'love'), 3: ('love',), 255: ('separation', 'hope'),
            268: ('separation', 'road'), 73: ('road', 'love'),
        }
        picks = {}
        for row in json.loads(path.read_text(encoding='utf-8')):
            number = int(row['source_url'].rsplit('/sh', 1)[1])
            book, _ = TreasuryBook.objects.get_or_create(slug=row['book'], defaults={
                'author': row['author'], 'source_url': f"https://ganjoor.net/{row['book']}",
                'has_contents': True, 'publishes_text': True, 'edition_note': 'https://ganjoor.net/faq?id=21',
            })
            entry, created = TreasuryEntry.objects.get_or_create(book=book, key=row['key'], defaults={
                **{key: row[key] for key in ('title', 'source_url', 'paragraphs', 'position')}, 'kind': 'work',
            })
            if created:
                book.work_count = book.entries.filter(kind='work').count()
                book.save(update_fields=['work_count'])
            if not book.publishes_text or not entry.couplets:
                raise CommandError(f'Work {book.slug}/{entry.key} is not available as complete couplets.')
            pick, created = TreasuryPick.objects.get_or_create(entry=entry, defaults={
                'published': True, 'featured': number != 73,
            })
            if created:
                pick.topics.set([topics[slug] for slug in assignments[number]])
            picks[number] = pick

        collection, created = TreasurySet.objects.get_or_create(slug='return', defaults={
            'title': 'آرزوی بازگشت', 'description': 'دو تصویر از امید به بازگشت و اضطرابِ رفتن.', 'published': True,
        })
        if created:
            TreasurySetVerse.objects.bulk_create([
                TreasurySetVerse(collection=collection, pick=picks[255], verse=1, order=1,
                                 commentary='بازگشت یوسف امکانِ دگرگون‌شدن اندوه را پیش چشم می‌آورد.'),
                TreasurySetVerse(collection=collection, pick=picks[268], verse=1, order=2,
                                 commentary='سعدی با خطاب به ساربان می‌کوشد لحظهٔ جدایی را به تعویق بیندازد.'),
            ])
        road, created = TreasurySet.objects.get_or_create(slug='journey', defaults={
            'title': 'راهِ دور', 'description': 'سفر در شعر حافظ و سعدی از منزل جانان تا کاروان.', 'published': True,
        })
        if created:
            TreasurySetVerse.objects.bulk_create([
                TreasurySetVerse(collection=road, pick=picks[1], verse=3, order=1,
                                 commentary='صدای جرس فرصت آرام‌گرفتن در منزل جانان را کوتاه می‌کند.'),
                TreasurySetVerse(collection=road, pick=picks[73], verse=9, order=2,
                                 commentary='ساربان زمام سفر را دارد و سنگینی دوری بر دل عاشق می‌ماند.'),
            ])
        TreasuryVerseLink.objects.get_or_create(origin=picks[268], origin_verse=1, target=picks[73],
            target_verse=9, kind=TreasuryVerseLink.Kind.IMAGE, defaults={
                'explanation': 'در هر دو بیت، گوینده از ساربان می‌خواهد آهسته برود تا جدایی دیرتر فرا برسد.',
            })
        self.stdout.write(self.style.SUCCESS(f'{len(picks)} starter works are available for editorial review.'))
