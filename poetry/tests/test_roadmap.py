import json
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from memorization.models import MemorizationItem, ReviewLog
from poetry.models import Collection, FavoriteVerse, LibraryImport, Poem, PoemEditRequest, TreasuryBook, TreasuryEntry, Verse
from poetry.services.edit_requests import decide_edit
from poetry.services.tags import save_tag


class RoadmapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reader = User.objects.create_user(username='reader')
        cls.other = User.objects.create_user(username='other')
        cls.poem = Poem.objects.create(owner=cls.reader, title='آزمایش', poet_name='شاعر')
        cls.first = Verse.objects.create(poem=cls.poem, position=1, hemistich_1='ردیف اول')
        cls.second = Verse.objects.create(poem=cls.poem, position=2, hemistich_1='زندگیِ دیگر', hemistich_2='مي رود کنار گل')
        cls.book = TreasuryBook.objects.create(slug='author', author='شاعر گنجینه', publishes_text=True,
                                                source_url='https://example.org/book', dataset_digest='a' * 64)
        cls.work = TreasuryEntry.objects.create(book=cls.book, kind='work', title='اثر نمونه', key='poem-1',
                                                position=1, paragraphs=['گل مي رود', 'ردیف دوم', 'نمونه سوم', 'نمونه چهارم'])

    def setUp(self):
        self.client.force_login(self.reader)

    def test_library_search_finds_variant_and_links_to_matching_verse(self):
        other = Poem.objects.create(owner=self.other, title='شعر خصوصی', poet_name='شاعر')
        Verse.objects.create(poem=other, position=1, hemistich_1='می‌رود')
        response = self.client.get(reverse('poems'), {'q': 'می‌رود'})
        self.assertContains(response, 'مي رود کنار گل')
        self.assertNotContains(response, other.title)
        detail = self.client.get(self.poem.get_absolute_url(), {'from': response.wsgi_request.get_full_path()})
        self.assertEqual(detail.context['library_back'], response.wsgi_request.get_full_path())

    def test_multiple_cards_remain_available_and_ranges_are_unique(self):
        MemorizationItem.objects.create(owner=self.reader, poem=self.poem, scope='full')
        self.assertContains(self.client.get(self.poem.get_absolute_url()), 'حفظ یک بازه')
        payload = {'poem_id': self.poem.pk, 'scope': 'range', 'start_verse_id': self.first.pk, 'end_verse_id': self.second.pk}
        response = self.client.post(reverse('item-new'), payload, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post(reverse('item-new'), payload, HTTP_ACCEPT='application/json').status_code, 409)
        self.assertEqual(self.poem.items.count(), 2)

    def test_new_line_layout_ignores_trailing_empty_structured_row(self):
        response = self.client.post(reverse('poem-new'), {'poet_name': 'شاعر نو', 'line_layout': 'on',
                                    'input_mode': 'structured', 'hemistich_1': ['خط شعر', ''], 'hemistich_2': ['', '']})
        self.assertEqual(response.status_code, 302)
        poem = Poem.objects.get(poet_name='شاعر نو')
        self.assertTrue(poem.line_layout)
        self.assertEqual(poem.verses.count(), 1)

    def test_treasury_search_excludes_unpublished_body_and_includes_metadata(self):
        hidden_book = TreasuryBook.objects.create(slug='hidden', author='شاعر دیگر')
        hidden = TreasuryEntry.objects.create(book=hidden_book, kind='work', title='اثر بی‌متن', key='private',
                                               position=1, paragraphs=['گل می‌رود', 'دادهٔ آزمایش'])
        search = reverse('treasury-works')
        self.assertContains(self.client.get(search, {'q': 'گل می‌رود'}), self.work.title)
        self.assertNotContains(self.client.get(search, {'q': 'گل می‌رود'}), hidden.title)
        response = self.client.get(search, {'q': hidden.title})
        self.assertContains(response, hidden.title)
        self.assertContains(response, 'فقط نمایه')
        self.assertNotContains(self.client.get(hidden.get_absolute_url()), 'دادهٔ آزمایش')

    def test_origin_merge_is_repeatable_and_does_not_change_existing_verse_ids(self):
        url = reverse('treasury-save', args=[self.book.slug, self.work.key])
        self.client.post(url, {'action': 'library', 'verse': ['2']})
        poem = Poem.objects.get(owner=self.reader, treasury_entry_key=self.work.key)
        first_id = poem.verses.get().pk
        payload = {'action': 'merge', 'merge_poem': poem.pk, 'verse': ['1', '2']}
        for _ in range(2):
            self.assertEqual(self.client.post(url, payload, HTTP_ACCEPT='application/json').status_code, 200)
        poem.refresh_from_db()
        self.assertEqual(poem.treasury_positions, [2, 1])
        self.assertEqual(list(poem.verses.values_list('pk', flat=True))[0], first_id)
        self.assertEqual(list(poem.verses.values_list('treasury_position', flat=True)), [2, 1])

    def test_collection_reorder_and_ownership(self):
        favorite = FavoriteVerse.objects.create(owner=self.reader, verse=self.first)
        foreign_poem = Poem.objects.create(owner=self.other, title='دیگری', poet_name='دیگری')
        self.client.post(reverse('collections'), {'name': 'برای خواندن'})
        collection = Collection.objects.get(owner=self.reader)
        self.client.post(collection.get_absolute_url(), {'action': 'add', 'poem': [self.poem.pk, foreign_poem.pk],
                                                          'favorite': favorite.pk})
        self.assertEqual(collection.items.count(), 2)
        second = collection.items.last()
        self.client.post(collection.get_absolute_url(), {'action': 'up', 'item': second.pk})
        self.assertEqual(collection.items.first().pk, second.pk)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(collection.get_absolute_url()).status_code, 404)

    def test_transfer_requires_preview_and_reimport_does_not_duplicate(self):
        topic = save_tag(self.reader, 'بهار')
        self.poem.tags.add(topic)
        FavoriteVerse.objects.create(owner=self.reader, verse=self.second)
        empty_topic = save_tag(self.reader, 'هنوز بدون شعر')
        now = timezone.now()
        card = MemorizationItem.objects.create(owner=self.reader, poem=self.poem, scope='range', start_verse=self.first,
                                               end_verse=self.second, review_count=1, last_reviewed_at=now)
        ReviewLog.objects.create(item=card, request_id=uuid4(), rating='good', reviewed_at=now,
                                 previous_due_at=now, next_due_at=now, previous_interval_days=0, next_interval_days=1)
        export = self.client.get(reverse('library-export', args=['json']))
        content = b''.join(export.streaming_content)
        self.assertEqual(json.loads(content)['poems'][0]['favorites'], [2])
        self.client.force_login(self.other)
        url = reverse('library-transfer')
        for attempt in range(2):
            self.client.post(url, {'action': 'preview', 'file': SimpleUploadedFile('library.json', content)})
            self.assertEqual(Poem.objects.filter(owner=self.other).count(), attempt)
            stage = LibraryImport.objects.get(owner=self.other)
            self.client.post(url, {'action': 'apply', 'revision': stage.created_at.isoformat()})
        imported = Poem.objects.get(owner=self.other)
        self.assertEqual(imported.tags.get().name, topic.name)
        self.assertEqual(FavoriteVerse.objects.get(owner=self.other).verse.position, 2)
        self.assertTrue(self.other.tag_set.filter(name=empty_topic.name).exists())
        restored = imported.items.get()
        self.assertEqual((restored.start_verse.position, restored.end_verse.position), (1, 2))
        self.assertEqual(restored.logs.get().rating, 'good')
        self.assertEqual(restored.review_count, 1)

    def test_edit_history_and_retry_are_private(self):
        edit = PoemEditRequest.objects.create(
            poem=self.poem, requested_by=self.reader, poem_updated_at=self.poem.updated_at,
            payload={'title': 'عنوان پیشنهادی', 'poet_name': 'شاعر', 'source_url': '', 'notes': '',
                     'tags': [], 'new_tag': '', 'topics': [], 'verses': [['ردیف اول', ''], ['سطر دوم', '']]},
        )
        reviewer = User.objects.create_superuser(username='reviewer', password='secret')
        decide_edit(edit, reviewer, approve=False, rejection_reason='منبع را بررسی کنید.')
        detail = reverse('edit-history-detail', args=[edit.pk])
        self.assertContains(self.client.get(detail), 'منبع را بررسی کنید.')
        self.assertContains(self.client.get(self.poem.get_absolute_url() + f'edit/?retry={edit.pk}'), 'عنوان پیشنهادی')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(detail).status_code, 404)

    def test_practice_and_stats_use_real_review_history(self):
        card = MemorizationItem.objects.create(owner=self.reader, poem=self.poem, scope='full')
        self.assertContains(self.client.get(reverse('review'), {'mode': 'blanks'}), 'واژهٔ جاافتاده')
        self.assertContains(self.client.get(reverse('review'), {'mode': 'progressive'}), 'نمایش ردیف ۲')
        now = timezone.now()
        ReviewLog.objects.create(item=card, request_id=uuid4(), rating='again', reviewed_at=now,
                                 previous_due_at=now, next_due_at=now, previous_interval_days=1, next_interval_days=0)
        self.assertContains(self.client.get(reverse('study-stats')), '۱ بار')

    def test_treasury_pick_preserves_selected_personal_poem(self):
        other = Poem.objects.create(owner=self.reader, title='دفتر دیگر', poet_name='شاعر')
        Verse.objects.create(poem=other, position=1, hemistich_1='متن دیگر')
        response = self.client.get(reverse('discover'), {'keep_poem': self.poem.pk, 'treasury_exclude': self.work.pk})
        self.assertEqual(response.context['poem'], self.poem)
