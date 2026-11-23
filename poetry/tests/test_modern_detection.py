from django.test import SimpleTestCase
from poetry.treasury_forms import is_line_poem, normalize_label


class ModernDetectionTests(SimpleTestCase):
    def test_modern_sections_override_unrecognized_nima_ids(self):
        self.assertTrue(is_line_poem('nima-ivshij', 'new-source-id', 'ققنوس', [('new-category', 'شعرهای نیمایی')]))

    def test_direct_labels_and_unicode_spacing(self):
        for title in ['شعر نو', 'شعرهای\u200cنو', 'اشعار   سپید', 'شعرهای آزاد', 'نيمایي']:
            self.assertTrue(is_line_poem('unknown', 'work', title, []), title)
        self.assertEqual(normalize_label('  شعرهاي\u200c نو '), 'شعرهای نو')

    def test_classical_titles_remain_classical_in_modern_collections(self):
        for title in ['غزل ۱', 'رباعی', 'مثنوی: آزمایش', 'قطعه ۲']:
            self.assertFalse(is_line_poem('shrab-sphri', 'work', title, [('modern', 'شعر نو')]))


from django.test import TestCase
from poetry.models import TreasuryBook, TreasuryEntry
from poetry.treasury_views import line_work_query


class ModernReadingTests(TestCase):
    def test_new_nima_work_is_read_and_discovered_as_separate_lines(self):
        book = TreasuryBook.objects.create(slug='nima-ivshij', author='نیما', publishes_text=True)
        section = TreasuryEntry.objects.create(book=book, key='new-section', title='شعرهای\u200cنو', kind='section', position=1)
        poem = TreasuryEntry.objects.create(book=book, parent=section, key='new-work', title='ققنوس', kind='work', position=1, paragraphs=['سطر اول\nسطر دوم', 'سطر سوم'])
        self.assertEqual(poem.reading_count, 3)
        self.assertTrue(TreasuryEntry.objects.filter(pk=poem.pk).filter(line_work_query()).exists())
        response = self.client.get(poem.get_absolute_url())
        self.assertTrue(response.context['line_layout'])
        self.assertEqual(response.context['rows'], [('سطر اول', ''), ('سطر دوم', ''), ('سطر سوم', '')])
        self.assertContains(response, 'verse-line', count=3)
