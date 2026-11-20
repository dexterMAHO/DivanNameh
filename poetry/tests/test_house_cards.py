from django.contrib.auth import get_user_model
from django.test import TestCase

from memorization.models import MemorizationItem
from poetry.models import FavoriteVerse, Poem, TreasuryBook, Verse


class HouseCardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('house-reader')
        self.client.force_login(self.user)
        self.poem = Poem.objects.create(owner=self.user, title='نمونه', poet_name='حافظ')
        self.verse = Verse.objects.create(poem=self.poem, position=1, hemistich_1='بیت نمونه')
        TreasuryBook.objects.create(slug='hafez', author='حافظ', portrait='img/poets/hafez.webp')

    def test_portrait_and_personal_badges(self):
        MemorizationItem.objects.create(owner=self.user, poem=self.poem, scope='full')
        FavoriteVerse.objects.create(owner=self.user, verse=self.verse)
        response = self.client.get('/poems/')
        self.assertContains(response, 'img/poets/hafez.webp')
        self.assertContains(response, 'house-window-star is-favorite')
        self.assertContains(response, 'aria-label="در فهرست حفظ"')
        self.assertNotContains(response, 'house-heading-icon')

    def test_other_accounts_do_not_set_badges_and_pagination_keeps_filters(self):
        other = get_user_model().objects.create_user('other-house-reader')
        MemorizationItem.objects.create(owner=other, poem=self.poem, scope='full')
        FavoriteVerse.objects.create(owner=other, verse=self.verse)
        Poem.objects.bulk_create([Poem(owner=self.user, title='نمونه', poet_name='حافظ') for _ in range(20)])
        response = self.client.get('/poems/?q=نمونه')
        self.assertNotContains(response, 'house-window-star is-favorite')
        self.assertNotContains(response, 'aria-label="در فهرست حفظ"')
        self.assertContains(response, 'pagination house-pagination')
        self.assertContains(response, 'q=%D9%86%D9%85%D9%88%D9%86%D9%87&amp;page=2')
