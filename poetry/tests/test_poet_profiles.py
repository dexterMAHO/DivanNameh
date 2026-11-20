from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from memorization.models import MemorizationItem
from poetry.models import FavoriteVerse, Poem, TreasuryBook, Verse


class PoetProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('poet-reader')
        self.other = get_user_model().objects.create_user('other-poet-reader')
        self.client.force_login(self.user)
        self.poem = Poem.objects.create(owner=self.user, poet_name='حافظ', title='شعر من')
        verse = Verse.objects.create(poem=self.poem, position=1, hemistich_1='بیت نمونه')
        FavoriteVerse.objects.create(owner=self.user, verse=verse)
        MemorizationItem.objects.create(owner=self.user, poem=self.poem, scope='full')
        TreasuryBook.objects.create(slug='hafez', author='حافظ', biography='زندگی‌نامهٔ شاعر', portrait='img/poets/hafez.webp')

    def test_gallery_and_profile_show_existing_data(self):
        Poem.objects.create(owner=self.user, poet_name='حافظ', title='شعر دوم')
        gallery = self.client.get(reverse('poets'))
        self.assertContains(gallery, 'شاعرنشین')
        self.assertContains(gallery, 'img/poets/hafez.webp')
        response = self.client.get(reverse('poet-profile'), {'name': 'حافظ'})
        self.assertContains(response, 'زندگی‌نامهٔ شاعر')
        self.assertEqual(response.context['poem_count'], 2)
        self.assertEqual(response.context['favorite_count'], 1)
        self.assertEqual(response.context['memory_count'], 1)

    def test_profile_only_shows_current_users_active_poems(self):
        Poem.objects.create(owner=self.other, poet_name='حافظ', title='شعر خصوصی دیگری')
        Poem.objects.create(owner=self.other, poet_name='شاعر دیگر')
        response = self.client.get(reverse('poet-profile'), {'name': 'حافظ'})
        self.assertNotContains(response, 'شعر خصوصی دیگری')
        self.assertEqual(self.client.get(reverse('poet-profile'), {'name': 'شاعر دیگر'}).status_code, 404)

    def test_unknown_poet_has_profile_without_invented_biography(self):
        Poem.objects.create(owner=self.user, poet_name='شاعر تازه')
        response = self.client.get(reverse('poet-profile'), {'name': 'شاعر تازه'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['profile'])
