from django.contrib.auth import get_user_model
from django.test import TestCase

from poetry.management.commands.fetch_poet_profiles import (
    candidate_titles, clean_metadata, describes_person, lunar_century, summarise,
)
from memorization.models import MemorizationItem
from poetry.models import FavoriteVerse, Poem, TreasuryBook, TreasuryEntry
from poetry.templatetags.persian import persian, tally


def make_book(slug='hafez', author='حافظ', **fields):
    return TreasuryBook.objects.create(
        slug=slug, author=author, source_url=f'https://i.ganjoor.net/epub/{slug}.epub',
        has_contents=True, dataset_digest='x' * 64, **fields)


class TreasuryPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('reader', password='test-secret-314159')
        cls.hafez = make_book(
            biography='شاعر فارسی‌گوی ایرانی سدهٔ هشتم.', biography_source='https://fa.wikipedia.org/wiki/حافظ',
            portrait='img/poets/hafez.webp', portrait_width=315, portrait_height=560,
            portrait_credit='ویکی‌مدیا کامنز', portrait_source='https://commons.wikimedia.org/wiki/File:X.jpg',
            birth_year=726, death_year=792, birth_place='شیراز', century=8, section_count=1, work_count=2,
            publishes_text=True, edition_note='https://ganjoor.net/faq?id=21')
        cls.saadi = make_book('saadi', 'سعدی', century=7, work_count=5, birth_place='شیراز')
        cls.root = TreasuryEntry.objects.create(book=cls.hafez, key='cat1', title='حافظ', position=0, kind='section')
        cls.ghazal = TreasuryEntry.objects.create(
            book=cls.hafez, parent=cls.root, key='poem-1', title='غزل ۱', position=1, kind='work',
            source_url='https://ganjoor.net/hafez/ghazal/sh1', paragraphs=['مصرع نخست', 'مصرع دوم'])

    def setUp(self):
        self.client.force_login(self.user)

    def test_index_lists_poets_with_profile(self):
        response = self.client.get('/treasury/')
        self.assertContains(response, 'حافظ')
        self.assertContains(response, 'شاعر فارسی‌گوی ایرانی سدهٔ هشتم.')
        self.assertContains(response, 'img/poets/hafez.webp')
        self.assertContains(response, '۲ شاعر یافت شد')

    def test_index_filters(self):
        for params, expected, missing in [
            ({'q': 'سعدی'}, 'سعدی', 'حافظ'),
            ({'q': 'سدهٔ هشتم'}, 'حافظ', 'سعدی'),
            ({'letter': 'س'}, 'سعدی', 'حافظ'),
            ({'century': '8'}, 'حافظ', 'سعدی'),
        ]:
            with self.subTest(params=params):
                response = self.client.get('/treasury/', params)
                self.assertContains(response, expected)
                self.assertNotContains(response, f'<span class="poet-name">{missing}</span>')

    def test_index_sorts_by_work_count(self):
        response = self.client.get('/treasury/', {'sort': 'works'})
        self.assertLess(response.content.index('سعدی'.encode()), response.content.index('حافظ'.encode()))

    def test_unknown_filters_are_ignored(self):
        response = self.client.get('/treasury/', {'letter': 'Z', 'century': 'x', 'sort': 'pk'})
        self.assertContains(response, '۲ شاعر یافت شد')

    def test_book_page_shows_profile_and_skips_single_root(self):
        response = self.client.get('/treasury/hafez/')
        self.assertContains(response, 'زادهٔ شیراز')
        self.assertContains(response, '۷۲۶ – ۷۹۲ ق')
        self.assertContains(response, 'https://fa.wikipedia.org/wiki/')
        # The lone wrapper section is skipped so its works are listed straight away.
        self.assertContains(response, 'غزل ۱')

    def test_book_page_never_links_the_epub_download(self):
        for url in ['/treasury/', '/treasury/hafez/', '/treasury/hafez/poem-1/']:
            with self.subTest(url=url):
                self.assertNotContains(self.client.get(url), 'i.ganjoor.net/epub')

    def test_work_page_renders_couplets_without_sending_readers_away(self):
        response = self.client.get('/treasury/hafez/poem-1/')
        self.assertContains(response, 'class="hemistich">مصرع نخست')
        self.assertContains(response, 'class="hemistich">مصرع دوم')
        # The stored text replaces the old "read it on Ganjoor" link.
        self.assertNotContains(response, 'https://ganjoor.net/hafez/ghazal/sh1')

    def test_work_without_text_still_points_at_the_source(self):
        TreasuryEntry.objects.create(
            book=self.hafez, parent=self.root, key='poem-2', title='غزل ۲', position=2, kind='work',
            source_url='https://ganjoor.net/hafez/ghazal/sh2')
        response = self.client.get('/treasury/hafez/poem-2/')
        self.assertContains(response, 'https://ganjoor.net/hafez/ghazal/sh2')

    def test_nested_works_are_all_listed_and_grouped(self):
        section = TreasuryEntry.objects.create(
            book=self.hafez, parent=self.root, key='section-2', title='قصیده‌ها', position=2, kind='section')
        TreasuryEntry.objects.bulk_create([
            TreasuryEntry(book=self.hafez, parent=section, key=f'work-{i}', title=f'قصیده شماره {i} پایان',
                          position=i, kind='work', paragraphs=['یک مصرع', 'پایانِ ي!'])
            for i in range(65)
        ])
        response = self.client.get('/treasury/hafez/', {'page': 2})
        self.assertContains(response, 'غزل ۱')
        self.assertContains(response, 'قصیده شماره 0 پایان')
        self.assertContains(response, 'قصیده شماره 64 پایان')
        self.assertContains(response, '<span>ی</span>', html=True)

    def test_selected_couplets_preserve_source_order_and_are_saved_once(self):
        self.ghazal.paragraphs += ['سطر سوم', 'سطر چهارم', 'سطر پنجم', 'سطر ششم']
        self.ghazal.save(update_fields=['paragraphs'])
        url = '/treasury/hafez/poem-1/save/'
        self.assertEqual(self.client.post(url, {'action': 'library', 'verse': ['3', '1', '3']}).status_code, 302)
        self.client.post(url, {'action': 'library', 'verse': ['1', '3']})
        poem = Poem.objects.get(owner=self.user)
        self.assertEqual(list(poem.verses.values_list('hemistich_1', flat=True)), ['مصرع نخست', 'سطر پنجم'])
        self.assertEqual(poem.source_url, self.ghazal.source_url)
        self.client.post(url, {'action': 'memorize', 'verse': ['3', '1']})
        self.assertTrue(MemorizationItem.objects.filter(owner=self.user, poem=poem).exists())

    def test_whole_poem_and_single_favorite(self):
        url = '/treasury/hafez/poem-1/save/'
        self.assertEqual(self.client.post(url, {'action': 'library-all'}).status_code, 302)
        self.client.post(url, {'action': 'favorite:1'})
        self.client.post(url, {'action': 'favorite:1'})
        self.assertEqual(FavoriteVerse.objects.get(owner=self.user).verse.hemistich_1, 'مصرع نخست')
        self.assertEqual(self.client.post(url, {'action': 'library', 'verse': ['2']}).status_code, 400)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_header_theme_persists_and_returns_to_work(self):
        target = self.ghazal.get_absolute_url()
        self.assertRedirects(self.client.post('/settings/theme/', {'theme': 'dark', 'next': target}), target)
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, 'dark')
        self.assertContains(self.client.get(target), 'data-theme="dark"')

    def test_missing_book_is_not_found(self):
        self.assertEqual(self.client.get('/treasury/unknown/').status_code, 404)

    def test_treasury_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get('/treasury/').status_code, 302)


class TreasuryModelTests(TestCase):
    def test_life_span_covers_partial_dates(self):
        self.assertEqual(make_book(birth_year=726, death_year=792).life_span, '726 – 792 ق')
        self.assertEqual(make_book('a', 'الف', death_year=792).life_span, 'درگذشتهٔ 792 ق')
        self.assertEqual(make_book('b', 'ب', birth_year=726).life_span, 'زادهٔ 726 ق')
        self.assertEqual(make_book('c', 'ج').life_span, '')

    def test_initial_skips_joiners(self):
        self.assertEqual(make_book('d', '‌آذر بیگدلی').initial, 'آ')

    def test_couplets_pair_hemistichs_but_leave_prose_alone(self):
        book = make_book()
        verse = TreasuryEntry(book=book, key='p1', title='غزل', position=0, kind='work',
                              paragraphs=['یک', 'دو', 'سه', 'چهار'])
        self.assertEqual(verse.couplets, [('یک', 'دو'), ('سه', 'چهار')])
        prose = TreasuryEntry(book=book, key='p2', title='مقدمه', position=1, kind='work',
                              paragraphs=['الف' * 60, 'ب'])
        self.assertIsNone(prose.couplets)
        self.assertIsNone(TreasuryEntry(book=book, key='p3', title='x', position=2, kind='work',
                                        paragraphs=['تک مصرع']).couplets)


class PersianFilterTests(TestCase):
    def test_digits_and_grouping(self):
        self.assertEqual(persian(1395), '۱۳۹۵')
        self.assertEqual(tally(144220), '۱۴۴٬۲۲۰')
        self.assertEqual(tally('—'), '—')


class ProfileFetchTests(TestCase):
    def test_summarise_keeps_opening_sentences(self):
        extract = 'یک. ' * 40
        self.assertEqual(summarise(extract), 'یک. یک. یک.')
        self.assertEqual(summarise(''), '')

    def test_summarise_truncates_a_single_long_sentence(self):
        summary = summarise('الف' * 400)
        self.assertTrue(summary.endswith('…'))
        self.assertLessEqual(len(summary), 421)

    def test_person_detection(self):
        self.assertTrue(describes_person('حافظ شاعر ایرانی بود'))
        self.assertFalse(describes_person('روستایی در استان فارس است'))

    def test_candidate_titles_prefer_the_full_name(self):
        book = TreasuryBook(slug='nezami', author='نظامی')
        self.assertEqual(candidate_titles(book, {'name': 'نظامی گنجوی'}), ['نظامی گنجوی', 'نظامی'])
        self.assertEqual(candidate_titles(book, {}), ['نظامی'])
        self.assertEqual(candidate_titles(book, {'name': 'نظامی'}), ['نظامی'])

    def test_clean_metadata_strips_markup_and_duplication(self):
        self.assertEqual(clean_metadata('<a href="#">Unknown photographer</a>Unknown photographer'),
                         'Unknown photographer')
        self.assertEqual(clean_metadata('<span>CC BY-SA 4.0</span>'), 'CC BY-SA 4.0')

    def test_lunar_century(self):
        self.assertEqual(lunar_century(None, 726), 8)
        self.assertEqual(lunar_century(800, 750), 8)
        self.assertIsNone(lunar_century(None, None))
