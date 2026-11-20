from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from poetry.models import ExplorePost, ExploreLike, ExploreSave, Poem


class ExplorePostsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('poster', action_password=make_password('test-action-123'))
        self.client.force_login(self.user)
        self.payload = {'title': 'عنوان', 'poet_name': 'شاعر', 'text': 'نخست | دوم\nسوم | چهارم'}

    def test_password_or_admin_approval_required(self):
        self.client.post('/explore/publish/', self.payload)
        pending = ExplorePost.objects.get()
        self.assertEqual(pending.status, 'pending')
        self.assertEqual(self.client.get(pending.get_absolute_url()).status_code, 404)
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
