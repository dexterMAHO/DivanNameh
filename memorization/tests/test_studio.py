from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from memorization.models import MemorizationItem, ReviewLog
from poetry.models import Poem, Verse


class StudyStudioTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('study-studio')
        self.client.force_login(self.user)
        self.poem = Poem.objects.create(owner=self.user, poet_name='شاعر', title='شعر')
        self.first = Verse.objects.create(poem=self.poem, position=1, hemistich_1='آغاز شعر')
        self.second = Verse.objects.create(poem=self.poem, position=2, hemistich_1='آغاز بازهٔ انتخابی')
        self.item = MemorizationItem.objects.create(owner=self.user, poem=self.poem, scope='full')

    def test_overview_counts_ignore_selected_tab(self):
        MemorizationItem.objects.create(owner=self.user, poem=self.poem, scope='range', start_verse=self.second,
            end_verse=self.second, due_at=timezone.now() + timedelta(days=2))
        response = self.client.get('/memorize/?state=upcoming')
        self.assertEqual(response.context['study_summary'], {'total': 2, 'ready': 1, 'upcoming': 1, 'paused': 0})
        self.assertEqual(response.context['page'].paginator.count, 1)
        self.assertContains(response, 'آغاز بازهٔ انتخابی')

    def test_progress_is_based_on_current_users_real_history(self):
        now = timezone.now()
        ReviewLog.objects.create(item=self.item, request_id=uuid4(), rating='good', reviewed_at=now,
            previous_due_at=now, next_due_at=now, previous_interval_days=0, next_interval_days=1)
        response = self.client.get('/review/')
        self.assertEqual(response.context['today_reviews'], 1)
        self.assertEqual(response.context['remaining'], 1)
        self.assertEqual(response.context['review_progress'], 50)
        self.assertContains(response, 'id="review-focus"')
