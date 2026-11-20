from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from memorization.models import MemorizationItem
from poetry.models import FavoriteVerse, Poem, TreasuryBook, TreasuryEntry, Verse
from poetry.services.discovery import choose_random_poem
from poetry.treasury_views import discover_work


class DiscoveryStudioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('discover-reader')
        cls.book = TreasuryBook.objects.create(slug='hafez-studio', author='حافظ', publishes_text=True, dataset_digest='edition')
        cls.modern_book = TreasuryBook.objects.create(slug='shrab-sphri', author='سهراب سپهری', publishes_text=True, dataset_digest='modern')
        cls.works = {}
        cls.poems = {}
        for count in (1, 2, 14, 15, 16):
            cls.works[count] = TreasuryEntry.objects.create(book=cls.book, key=f'work-{count}', title=f'غزل {count}',
                kind='work', position=count, paragraphs=[text for _ in range(count) for text in ('مصرع نخست', 'مصرع دوم')])
            poem = Poem.objects.create(owner=cls.user, title=f'شعر {count}', poet_name='حافظ')
            Verse.objects.bulk_create([Verse(poem=poem, position=n, hemistich_1='مصرع نخست', hemistich_2='مصرع دوم') for n in range(1, count + 1)])
            cls.poems[count] = poem
        cls.modern_work = TreasuryEntry.objects.create(book=cls.modern_book, key='modern', title='شعر نو', kind='work', position=1, paragraphs=['صدای پای آب', 'به سراغ من اگر می‌آیید'])
        cls.modern_poem = Poem.objects.create(owner=cls.user, title='شعر نو', poet_name='سهراب سپهری', line_layout=True)
        Verse.objects.create(poem=cls.modern_poem, position=1, hemistich_1='صدای پای آب')

    def setUp(self):
        self.client.force_login(self.user)

    def test_default_and_autocomplete(self):
        response = self.client.get(reverse('discover'))
        self.assertEqual(response.context['source'], 'treasury')
        self.assertIsNone(response.context['poem'])
        self.assertContains(response, '<option value="حافظ">', html=False)
        self.assertContains(response, 'list="discovery-poets"')
        for value in ('single', 'double', 'under15', 'over15', 'modern'):
            self.assertContains(response, f'value="{value}"')

    def test_lengths_in_both_sources_and_fifteen_boundary(self):
        for length, allowed in [('single', {1}), ('double', {2}), ('under15', {1, 2, 14}), ('over15', {16})]:
            with self.subTest(length=length):
                work = discover_work(None, length=length)
                self.assertIn(work['row_count'], allowed)
                self.assertFalse(work['line_layout'])
                poem = choose_random_poem(self.user, length=length)
                self.assertIn(poem.verses.count(), allowed)
                self.assertFalse(poem.line_layout)
                # A pinned 15-couplet poem cannot override a selected length.
                self.assertNotEqual(discover_work(None, length=length, keep_id=self.works[15].pk)['entry'], self.works[15])
                self.assertNotEqual(choose_random_poem(self.user, length=length, keep_id=self.poems[15].pk), self.poems[15])
        self.assertEqual(discover_work(None, length='modern')['entry'], self.modern_work)
        self.assertEqual(choose_random_poem(self.user, length='modern'), self.modern_poem)

    def test_partial_poet_search_and_guest_access(self):
        response = self.client.get(reverse('discover'), {'poet': 'سهراب', 'length': 'modern'})
        self.assertEqual(response.context['treasury_pick']['entry'], self.modern_work)
        self.client.logout()
        response = self.client.get(reverse('discover'), {'source': 'library'})
        self.assertEqual(response.context['source'], 'treasury')
        self.assertNotContains(response, 'data-discovery-action')

    def test_discovery_actions_reuse_one_full_poem(self):
        work = self.works[14]
        url = reverse('treasury-save', args=[work.book.slug, work.key])
        def post(action):
            response = self.client.post(url, {'action': action, 'from_discovery': '1'}, HTTP_ACCEPT='application/json')
            self.assertEqual(response.status_code, 200, response.content)
            return response
        post('favorite:2')
        post('library-all')
        post('memorize')
        post('memorize')
        imported = Poem.objects.get(owner=self.user, treasury_entry_key=work.key)
        self.assertEqual(imported.verses.count(), 14)
        self.assertEqual(FavoriteVerse.objects.get(owner=self.user).verse.treasury_position, 2)
        self.assertEqual(MemorizationItem.objects.filter(poem=imported).count(), 1)
        post('unfavorite:2')
        self.assertFalse(FavoriteVerse.objects.filter(owner=self.user).exists())
        self.assertTrue(Poem.objects.filter(pk=imported.pk).exists())

    def test_operation_password_and_modern_layout_are_preserved(self):
        self.user.action_password = make_password('review-password-314159')
        self.user.save()
        url = reverse('treasury-save', args=[self.modern_book.slug, self.modern_work.key])
        data = {'action': 'memorize', 'from_discovery': '1'}
        self.assertEqual(self.client.post(url, data, HTTP_ACCEPT='application/json').status_code, 403)
        self.assertFalse(Poem.objects.filter(treasury_entry_key=self.modern_work.key).exists())
        data['action_password'] = 'review-password-314159'
        self.assertEqual(self.client.post(url, data, HTTP_ACCEPT='application/json').status_code, 200)
        saved = Poem.objects.get(owner=self.user, treasury_entry_key=self.modern_work.key)
        self.assertTrue(saved.line_layout)
        self.assertEqual(saved.verses.count(), 2)

    def test_no_import_for_anonymous_or_unpublished_work(self):
        self.book.publishes_text = False
        self.book.save()
        url = reverse('treasury-save', args=[self.book.slug, self.works[1].key])
        self.assertEqual(self.client.post(url, {'action': 'library-all', 'from_discovery': '1'}, HTTP_ACCEPT='application/json').status_code, 400)
        self.client.logout()
        self.assertEqual(self.client.post(url, {'action': 'library-all', 'from_discovery': '1'}, HTTP_ACCEPT='application/json').status_code, 401)
