from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from memorization.models import MemorizationItem
from poetry.models import FavoriteVerse, Poem, PoemShare, TreasuryPick, Verse


class PublicTreasuryShareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_public_treasury', verbosity=0)
        model = get_user_model()
        cls.sender = model.objects.create_user(username='sender')
        cls.recipient = model.objects.create_user(username='recipient')

    def publish(self, path, payload):
        preview = self.client.post(path, payload)
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, 'پیش‌نمایش اشتراک')
        self.assertFalse(PoemShare.objects.exists())
        committed = self.client.post(path, {**payload, 'intent': 'confirm', 'preview': preview.context['preview']})
        self.assertEqual(committed.status_code, 302)
        return PoemShare.objects.get()

    def test_public_trace_to_shared_practice_to_recipient_review(self):
        trace = self.client.get(reverse('treasury-trace'), {'q': 'يوسف گم گشته'})
        hit = trace.context['page'][0]
        entry = hit['entry']
        self.assertEqual(hit['position'], 1)
        self.assertContains(trace, '<mark>')
        self.assertContains(trace, entry.couplets[0][1])
        self.assertContains(self.client.get(hit['url']), 'id="verse-1"')

        self.client.force_login(self.sender)
        path = reverse('share-treasury', args=[entry.book.slug, entry.key])
        share = self.publish(path, {'selection': 'selected', 'verse': '1', 'mode': 'practice', 'note': 'برای تو'})
        url = reverse('shared-poem', args=[share.token])
        friend = Client()
        self.assertNotContains(friend.get(url), entry.couplets[0][1])
        revealed = friend.post(url, {'intent': 'reveal'})
        self.assertContains(revealed, entry.couplets[0][1])
        self.assertContains(revealed, hit['url'])
        self.assertContains(revealed, 'افزودن به مرور من')
        self.assertContains(revealed, 'برای تو')
        card = friend.get(reverse('share-card', args=[share.token]))
        self.assertEqual(card['Content-Type'], 'image/png')
        self.assertTrue(b''.join(card.streaming_content).startswith(b'\x89PNG'))
        save = reverse('share-save', args=[share.token])
        self.assertEqual(friend.get(save + '?action=memorize').status_code, 302)
        friend.force_login(self.recipient)
        self.assertRedirects(friend.post(save, {'action': 'memorize'}), reverse('memorize'))
        self.assertRedirects(friend.post(save, {'action': 'memorize'}), reverse('memorize'))
        card = MemorizationItem.objects.get(owner=self.recipient)
        self.assertEqual(card.start_verse.treasury_position, 1)
        self.assertEqual(card.start_verse_id, card.end_verse_id)
        self.assertEqual(Poem.objects.filter(owner=self.sender).count(), 0)

    def test_public_filters_and_whole_poem_reuse(self):
        page = self.client.get(reverse('treasury'), {'q': 'سعدی'})
        self.assertTrue(page.context['page'])
        self.assertTrue(all(book.slug == 'saadi' for book in page.context['page']))
        self.assertNotContains(page, 'id="showcase"')
        self.assertNotContains(page, 'name="public_turn"')
        explore = self.client.get(reverse('explore'))
        self.assertNotContains(explore, 'منتخب‌های گنجینه')
        self.assertNotContains(explore, 'name="public_poet"')
        self.assertNotContains(explore, 'name="public_turn"')
        self.assertNotIn('treasury_pick', explore.context)
        chosen = self.client.get(reverse('explore'), {
            'public_poet': 'saadi', 'public_topic': 'separation', 'public_turn': '1',
        })
        entry = TreasuryPick.objects.get(entry__key='poem-9590').entry
        self.assertEqual(chosen.status_code, 200)
        self.assertNotIn('picks', chosen.context)
        self.assertContains(chosen, 'شعرجویی')
        random_page = self.client.get(reverse('discover'))
        self.assertContains(random_page, '<h1>کشف شعر</h1>', html=True)
        self.assertNotIn('picks', random_page.context)
        self.assertIsNotNone(random_page.context['treasury_pick'])
        self.assertEqual(random_page.context['source'], 'treasury')
        self.assertContains(self.client.get(entry.get_absolute_url()), 'از این بیت به آن بیت')
        self.client.force_login(self.sender)
        save = reverse('treasury-save', args=[entry.book.slug, entry.key])
        self.client.post(save, {'action': 'favorite:1'})
        self.client.post(save, {'action': 'library-all'})
        poem = Poem.objects.get(owner=self.sender)
        self.assertEqual(poem.verses.count(), len(entry.couplets))
        self.assertEqual(FavoriteVerse.objects.get(owner=self.sender).verse.poem, poem)

    def test_private_snapshot_survives_edits_and_can_be_revoked(self):
        poem = Poem.objects.create(owner=self.sender, poet_name='شاعر خصوصی', notes='یادداشت خصوصی')
        for position, text in enumerate(('بیت خصوصی', 'بیت دوم', 'بیت سوم', 'بیت چهارم'), 1):
            Verse.objects.create(poem=poem, position=position, hemistich_1=text, hemistich_2='مصرع دوم')
        path = reverse('share-library', args=[poem.pk])
        self.assertEqual(self.client.get(path).status_code, 302)
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.client.force_login(self.sender)
        payload = {'selection': 'selected', 'verse': ['4', '2'], 'note': 'یادداشت همراه'}
        self.assertContains(self.client.post(path, {**payload, 'intent': 'confirm'}), 'پیش‌نمایش را دوباره')
        share = self.publish(path, payload)
        poem.verses.filter(position=2).update(hemistich_1='ویرایش بعدی')
        url = reverse('shared-poem', args=[share.token])
        guest = Client().get(url)
        self.assertContains(guest, 'بیت دوم')
        self.assertContains(guest, 'share-gap')
        for hidden in ('بیت خصوصی', 'یادداشت خصوصی', 'ویرایش بعدی', 'بیت سوم'):
            self.assertNotContains(guest, hidden)
        revoke = reverse('share-revoke', args=[share.token])
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.post(revoke).status_code, 404)
        self.client.force_login(self.sender)
        self.assertRedirects(self.client.post(revoke), reverse('my-shares'))
        self.assertEqual(Client().get(url).status_code, 404)
