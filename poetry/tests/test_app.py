import uuid
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from poetry.models import Poem, PoemEditRequest, Verse, Tag, FavoriteVerse
from poetry.services.poem_editor import save_poem, parse_verses
from poetry.services.tags import save_tag
from memorization.models import MemorizationItem, ReviewLog
from memorization.services.selections import create_item
from memorization.services.reviews import rate_item


class AppTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('reader', password='test-secret-314159')
        cls.other = get_user_model().objects.create_user('other', password='test-secret-314159')

    def setUp(self):
        self.client.force_login(self.user)
        self.data = dict(title='نمونه', poet_name='شاعر نمونه', source_url='', notes='', tags=[])
        self.poem = save_poem(self.user, self.data, [('اول', 'دوم'), ('سوم', 'چهارم')])

    def post_poem(self, **changes):
        data = dict(title='', poet_name='نمونه', source_url='', notes='', input_mode='lines', bulk_text='الف | ب\nج')
        data.update(changes)
        return self.client.post(reverse('poem-new'), data)

    def test_pages_render(self):
        save_tag(self.user, 'عاشقانه')
        create_item(self.user, self.poem, 'full')
        FavoriteVerse.objects.create(owner=self.user, verse=self.poem.verses.first())
        for url in ['/', '/poems/', '/poems/?archived=1', f'/poems/{self.poem.pk}/', f'/poems/{self.poem.pk}/edit/',
                    '/poems/new/', '/tags/', '/tags/view/عاشقانه/', '/favorites/', '/memorize/', '/review/', '/discover/']:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'دیوان نامه')

    def test_parser(self):
        self.assertEqual(parse_verses('  الف\u200cب | ج \n\n نو ', 'lines'), [('الف\u200cب', 'ج'), ('نو', '')])
        self.assertEqual(parse_verses('الف\n\nب', 'pairs'), [('الف', 'ب')])
        for text, mode in [('', 'lines'), ('الف', 'pairs'), ('| ب', 'lines'), ('x' * 1001, 'lines')]:
            with self.assertRaises(ValidationError): parse_verses(text, mode)

    def test_create_and_invalid_input(self):
        response = self.post_poem()
        self.assertEqual(response.status_code, 302)
        poem = Poem.objects.exclude(pk=self.poem.pk).get()
        self.assertEqual(list(poem.verses.values_list('position', flat=True)), [1, 2])
        self.assertEqual(poem.display_title, 'الف')
        self.assertEqual(self.post_poem(poet_name='', bulk_text='متن باقی می‌ماند').status_code, 200)
        self.assertEqual(Poem.objects.count(), 2)
        response = self.post_poem(bulk_text='<script>alert(1)</script>')
        self.assertNotContains(self.client.get(response.url), '<script>alert(1)</script>')
        self.assertEqual(self.post_poem(source_url='javascript:alert(1)').status_code, 200)
        self.assertEqual(self.post_poem(source_url='ftp://example.com').status_code, 200)

    def test_structured_create(self):
        response = self.post_poem(input_mode='structured', hemistich_1=['یک', 'دو'], hemistich_2=['سه', ''])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Poem.objects.latest('pk').verses.count(), 2)

    def test_atomic_duplicate_tag(self):
        save_tag(self.user, 'تگ')
        count = Poem.objects.count()
        response = self.post_poem(new_tag='تگ')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Poem.objects.count(), count)

    def test_tags_normalization_slug_and_ownership(self):
        tag = save_tag(self.user, '  عاشقانه  ')
        with self.assertRaises(ValidationError): save_tag(self.user, 'عاشقانه')
        save_tag(self.user, 'كي')
        with self.assertRaises(ValidationError): save_tag(self.user, 'کی')
        punctuation = save_tag(self.user, '!!!')
        another = save_tag(self.user, '???')
        self.assertNotEqual(punctuation.slug, another.slug)
        foreign = save_tag(self.other, 'خصوصی')
        response = self.post_poem(tags=[foreign.pk])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post(reverse('poem-tags', args=[self.poem.pk]), {'tags': [foreign.pk]}).status_code, 400)
        self.assertEqual(self.client.post(reverse('tag-rename', args=[foreign.pk]), {'name': 'الف'}).status_code, 404)
        self.poem.tags.add(tag)
        self.assertContains(self.client.get(tag.get_absolute_url()), self.poem.title)
        self.client.post(reverse('tag-delete', args=[tag.pk]), {'confirm': 'yes'})
        self.assertTrue(Poem.objects.filter(pk=self.poem.pk).exists())

    def test_favorites_idempotence(self):
        verse = self.poem.verses.first()
        for _ in range(2): self.client.post(reverse('favorite', args=[verse.pk]))
        self.assertEqual(FavoriteVerse.objects.count(), 1)
        self.client.post(reverse('unfavorite', args=[verse.pk]))
        self.assertEqual(FavoriteVerse.objects.count(), 0)

    def test_edit_preserves_ids_resets_only_affected(self):
        first, second = list(self.poem.verses.all())
        full = create_item(self.user, self.poem, 'full')
        partial = create_item(self.user, self.poem, 'range', second, second)
        for item in [full, partial]: rate_item(self.user, item.pk, 'easy', uuid.uuid4())
        FavoriteVerse.objects.create(owner=self.user, verse=first)
        save_poem(self.user, self.data, [('اصلاح', 'دوم'), ('سوم', 'چهارم'), ('تازه', '')], self.poem)
        full.refresh_from_db(); partial.refresh_from_db(); first.refresh_from_db()
        self.assertEqual(first.hemistich_1, 'اصلاح')
        self.assertEqual(full.interval_days, 0)
        self.assertEqual(partial.interval_days, 3)
        self.assertEqual(full.review_count, 1)
        self.assertEqual(ReviewLog.objects.count(), 2)
        with self.assertRaises(ValidationError): save_poem(self.user, self.data, [('تک', '')], self.poem)

    def test_saved_poem_changes_only_after_admin_approval(self):
        self.user.action_password = make_password('action-test-password-271')
        self.user.save(update_fields=['action_password'])
        url = reverse('poem-edit', args=[self.poem.pk])
        data = {'title': 'عنوان تازه', 'poet_name': 'شاعر تازه', 'input_mode': 'lines', 'bulk_text': 'بیت اول\nبیت دوم'}
        self.assertContains(self.client.post(url, data), 'رمز عملیات درست نیست')
        self.assertFalse(PoemEditRequest.objects.exists())
        self.assertRedirects(self.client.post(url, {**data, 'action_password': 'action-test-password-271'}), self.poem.get_absolute_url())
        edit = PoemEditRequest.objects.get(poem=self.poem)
        self.poem.refresh_from_db()
        self.assertEqual(self.poem.title, self.data['title'])
        admin = get_user_model().objects.create_superuser('reviewer')
        self.client.force_login(admin)
        changelist = reverse('admin:poetry_poemeditrequest_changelist')
        detail_url = reverse('admin:poetry_poemeditrequest_change', args=[edit.pk])
        comparison = self.client.get(detail_url)
        self.assertContains(comparison, self.user.username)
        self.assertContains(comparison, self.data['title'])
        self.assertContains(comparison, data['title'])
        self.assertContains(comparison, 'نسخهٔ قبلی')
        response = self.client.post(changelist, {'action': 'approve_edits', '_selected_action': [edit.pk]}, follow=True)
        self.assertContains(response, 'درخواست بررسی شد')
        edit.refresh_from_db()
        self.poem.refresh_from_db()
        self.assertEqual(edit.status, PoemEditRequest.Status.APPROVED)
        self.assertEqual(edit.requested_by, self.user)
        self.assertContains(self.client.get(detail_url), self.data['title'])
        self.assertEqual(self.poem.title, data['title'])
        self.assertEqual(self.poem.verses.first().hemistich_1, 'بیت اول')

    def test_archive_restore_and_discovery(self):
        verse = self.poem.verses.first()
        FavoriteVerse.objects.create(owner=self.user, verse=verse)
        create_item(self.user, self.poem, 'full')
        self.client.post(reverse('poem-archive', args=[self.poem.pk]))
        self.poem.refresh_from_db()
        self.assertIsNone(self.poem.archived_at)
        self.user.action_password = make_password('action-test-password-271')
        self.user.save(update_fields=['action_password'])
        self.client.post(reverse('poem-archive', args=[self.poem.pk]), {'action_password': 'action-test-password-271'})
        self.assertEqual(self.client.get('/api/discover/random/').json()['poem'], None)
        self.assertContains(self.client.get('/review/'), 'مروری برای الان باقی نمانده')
        self.assertEqual(self.client.get('/favorites/').context['page'].paginator.count, 0)
        self.client.post(reverse('poem-restore', args=[self.poem.pk]))
        self.assertEqual(self.client.get('/favorites/').context['page'].paginator.count, 1)
        second = save_poem(self.user, self.data, [('تازه', '')])
        self.assertEqual(self.client.get(f'/api/discover/random/?exclude_id={self.poem.pk}').json()['poem']['id'], second.pk)

    def test_owner_isolation(self):
        foreign = save_poem(self.other, self.data, [('متن محرمانهٔ حساب دیگر', '')])
        item = create_item(self.other, foreign, 'full')
        for url in [foreign.get_absolute_url(), reverse('poem-edit', args=[foreign.pk])]:
            self.assertEqual(self.client.get(url).status_code, 404)
        actions = [reverse('poem-archive', args=[foreign.pk]), reverse('favorite', args=[foreign.verses.first().pk]),
                   reverse('item-delete', args=[item.pk]), reverse('rate', args=[item.pk])]
        for url in actions:
            self.assertEqual(self.client.post(url, {'confirm': 'yes'}).status_code, 404)
        self.assertNotContains(self.client.get('/poems/'), 'متن محرمانهٔ حساب دیگر')

    def test_csrf_auth_and_post_only(self):
        self.client.logout()
        self.assertEqual(self.client.get('/poems/').status_code, 302)
        self.assertEqual(self.client.get('/api/discover/random/', HTTP_ACCEPT='application/json').status_code, 401)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(reverse('favorite', args=[self.poem.verses.first().pk])).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('poem-archive', args=[self.poem.pk])).status_code, 405)
        self.assertEqual(self.client.get('/logout/').status_code, 405)
        self.assertEqual(self.client.post('/logout/').status_code, 302)

    def test_pagination(self):
        for i in range(21): save_poem(self.user, self.data, [(str(i), '')])
        page = self.client.get('/poems/').context['page']
        self.assertEqual(len(page), 20)
        self.assertTrue(page.has_next())
