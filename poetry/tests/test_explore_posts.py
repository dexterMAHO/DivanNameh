from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from poetry.models import ExplorePost, ExploreLike, ExploreSave, Poem, FavoriteVerse


class ExplorePostsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('poster', action_password=make_password('test-action-123'))
        self.client.force_login(self.user)
        self.payload = {'title': 'عنوان', 'poet_name': 'شاعر', 'text': 'نخست | دوم\nسوم | چهارم'}

    def test_password_or_admin_approval_required(self):
        self.client.post('/explore/publish/', self.payload)
        pending = ExplorePost.objects.get()
        self.assertEqual(pending.status, 'pending')
        self.assertEqual(self.client.get(pending.get_absolute_url()).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(pending.get_absolute_url()).status_code, 404)
        self.client.force_login(self.user)
        self.client.post('/explore/publish/', {**self.payload, 'action_password': 'wrong'})
        self.assertFalse(ExplorePost.objects.filter(status='published').exists())
        self.client.post('/explore/publish/', {**self.payload, 'action_password': 'test-action-123'})
        self.assertEqual(ExplorePost.objects.filter(status='published').count(), 1)

    def test_like_save_and_view_are_idempotent(self):
        post = ExplorePost.objects.create(author=self.user, title='عنوان', poet_name='شاعر', rows=[['الف','ب']], status='published')
        for _ in range(2):
            self.client.get(post.get_absolute_url())
            self.client.post(f'/explore/posts/{post.pk}/action/', {'intent': 'like'})
            self.client.post(f'/explore/posts/{post.pk}/action/', {'intent': 'save'})
        self.assertEqual(post.views.count(), 1)
        self.assertEqual(post.likes.count(), 1)
        self.assertEqual(post.saves.count(), 1)
        poem = Poem.objects.get(owner=self.user)
        self.assertEqual(poem.verses.first().hemistich_1, 'الف')
        self.client.post(f'/explore/posts/{post.pk}/action/', {'intent': 'unlike'})
        self.assertEqual(post.likes.count(), 0)
        poem.delete()
        self.client.post(f'/explore/posts/{post.pk}/action/', {'intent': 'save'})
        self.assertEqual(Poem.objects.filter(owner=self.user).count(), 1)

    def test_sorting_and_private_actions(self):
        first = ExplorePost.objects.create(author=self.user, title='اول', poet_name='شاعر', rows=[['الف','ب']], status='published')
        ExplorePost.objects.create(author=self.user, title='دوم', poet_name='شاعر', rows=[['الف','ب']], status='published')
        ExploreLike.objects.create(post=first, user=self.user)
        ExploreSave.objects.create(post=first, user=self.user)
        self.client.get(first.get_absolute_url())
        for sort in ('likes', 'saves', 'views'):
            response = self.client.get('/explore/', {'sort': sort})
            self.assertEqual(response.context['post_page'][0], first)
        self.client.logout()
        self.assertEqual(self.client.get('/explore/').status_code, 200)
        self.assertEqual(self.client.post(f'/explore/posts/{first.pk}/action/', {'intent': 'save'}).status_code, 302)
        self.assertEqual(self.client.get('/explore/publish/').status_code, 302)

    def test_input_modes_and_author_only_edit(self):
        self.client.post('/explore/publish/', {**self.payload, 'input_mode': 'pairs', 'text': 'یک\nدو\nسه\nچهار', 'action_password': 'test-action-123'})
        post = ExplorePost.objects.get()
        self.assertEqual(post.rows, [['یک', 'دو'], ['سه', 'چهار']])
        url = f'/explore/posts/{post.pk}/edit/'
        self.client.post(url, {**self.payload, 'title': 'ویرایش', 'input_mode': 'structured', 'hemistich_1': ['اول'], 'hemistich_2': ['دوم']})
        post.refresh_from_db()
        self.assertEqual(post.title, 'ویرایش')
        self.assertEqual(post.rows, [['اول', 'دوم']])
        self.assertEqual(post.status, 'pending')
        self.client.post(url, {**self.payload, 'action_password': 'test-action-123'})
        post.refresh_from_db()
        self.assertEqual(post.status, 'published')
        other = get_user_model().objects.create_user('other-poster')
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, self.payload).status_code, 404)

    def test_profile_photos_are_only_public_for_published_authors(self):
        from accounts.models import ProfilePhoto
        ProfilePhoto.objects.create(user=self.user, image=b'example-webp')
        post = ExplorePost.objects.create(author=self.user, title='عنوان', poet_name='شاعر', rows=[['الف', 'ب']])
        self.client.logout()
        photo_url = f'/explore/authors/{self.user.pk}/photo/'
        self.assertEqual(self.client.get(photo_url).status_code, 404)
        post.status = 'published'
        post.save()
        self.assertEqual(self.client.get(photo_url).status_code, 200)
        response = self.client.get('/explore/')
        self.assertContains(response, photo_url)
        self.assertContains(self.client.get(post.get_absolute_url()), photo_url)

    def test_direct_favorites_reuse_personal_poem_and_toggle_independently(self):
        from poetry.explore_views import _row_key
        post = ExplorePost.objects.create(author=self.user, title='منتخب', poet_name='شاعر',
            rows=[['الف', 'ب'], ['ج', 'د']], status='published')
        url = f'/explore/posts/{post.pk}/action/'
        payload = {'intent': 'favorite', 'position': 2, 'row_key': _row_key(post.rows[1])}
        for _ in range(2):
            response = self.client.post(url, payload, HTTP_ACCEPT='application/json')
            self.assertTrue(response.json()['favorite'])
        verse = FavoriteVerse.objects.get(owner=self.user).verse
        self.assertEqual((verse.hemistich_1, verse.hemistich_2), ('ج', 'د'))
        self.assertEqual(verse.poem.owner, self.user)
        self.assertEqual(post.saves.get(user=self.user).poem, verse.poem)
        self.client.post(url, {'intent': 'save'})
        self.assertEqual(Poem.objects.filter(owner=self.user).count(), 1)
        self.assertTrue(self.client.get('/explore/').context['post_page'][0].display_rows[1]['favorite'])
        self.assertTrue(self.client.get(post.get_absolute_url()).context['post'].display_rows[1]['favorite'])
        for _ in range(2):
            response = self.client.post(url, {**payload, 'intent': 'unfavorite'}, HTTP_ACCEPT='application/json')
            self.assertFalse(response.json()['favorite'])
        self.assertFalse(FavoriteVerse.objects.filter(owner=self.user).exists())
        self.assertTrue(Poem.objects.filter(pk=verse.poem_id).exists())

    def test_favorites_validate_row_and_preserve_edited_saved_text(self):
        from poetry.explore_views import _row_key
        post = ExplorePost.objects.create(author=self.user, title='منتخب', poet_name='شاعر',
            rows=[['الف', 'ب']], status='published')
        url = f'/explore/posts/{post.pk}/action/'
        payload = {'intent': 'favorite', 'position': 1, 'row_key': _row_key(post.rows[0])}
        for position in (0, -1, 2, 'invalid'):
            self.assertEqual(self.client.post(url, {**payload, 'position': position}).status_code, 400)
        self.assertEqual(self.client.post(url, {**payload, 'row_key': 'stale'}).status_code, 400)
        self.assertFalse(post.saves.exists())
        self.client.post(url, {'intent': 'save'})
        poem = post.saves.get().poem
        post.rows = [['متن تازه', 'مصرع تازه']]
        post.save()
        self.assertEqual(self.client.post(url, payload).status_code, 400)
        payload['row_key'] = _row_key(post.rows[0])
        self.client.post(url, payload)
        self.assertEqual(poem.verses.count(), 2)
        self.assertEqual(poem.verses.get(position=1).hemistich_1, 'الف')
        self.assertEqual(FavoriteVerse.objects.get().verse.hemistich_1, 'متن تازه')
        self.client.logout()
        self.assertEqual(self.client.post(url, payload, HTTP_ACCEPT='application/json').status_code, 401)
        self.client.force_login(self.user)
        post.status = 'pending'
        post.save()
        self.assertEqual(self.client.post(url, payload).status_code, 404)
