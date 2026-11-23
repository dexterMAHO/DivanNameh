import json
from xml.etree import ElementTree
from django.test import TestCase
from poetry.models import TreasuryBook, TreasuryEntry


class SeoTests(TestCase):
    def setUp(self):
        self.book = TreasuryBook.objects.create(slug='seo-poet', author='شاعر آزمایش', publishes_text=True)
        self.entry = TreasuryEntry.objects.create(book=self.book, key='poem', title='عنوان شعر', position=1, kind='work', paragraphs=['مصرع نخست', 'مصرع دوم'])

    def test_public_text_and_metadata(self):
        response = self.client.get(self.entry.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'مصرع نخست')
        self.assertContains(response, 'مصرع دوم')
        self.assertContains(response, 'index,follow')
        self.assertContains(response, 'rel="canonical"')
        self.assertContains(response, 'عنوان شعر — شاعر آزمایش')
        body = response.content.decode()
        data = body.split('<script type="application/ld+json">')[1].split('</script>')[0]
        self.assertEqual(json.loads(data)['author']['name'], self.book.author)
        self.assertNotIn('?q=', self.client.get(self.entry.get_absolute_url(), {'q': 'test'}).context['seo_canonical'])

    def test_sitemaps_are_valid_and_contain_public_poems_only(self):
        for url in ['/sitemap.xml', '/sitemap/pages.xml', '/sitemap/poems-1.xml']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            ElementTree.fromstring(response.content)
        self.assertContains(self.client.get('/sitemap/poems-1.xml'), self.entry.get_absolute_url())
        self.assertNotContains(self.client.get('/sitemap/pages.xml'), '/settings/')
        self.assertEqual(self.client.get('/sitemap/poems-999.xml').status_code, 404)
        self.assertContains(self.client.get('/robots.txt'), 'https://divannameh.com/sitemap.xml')

    def test_json_script_cannot_be_closed_by_title(self):
        self.entry.title = '</script><script>alert(1)</script>'
        self.entry.save()
        response = self.client.get(self.entry.get_absolute_url())
        self.assertNotContains(response, '</script><script>alert(1)</script>')
