import uuid
from datetime import timedelta
from types import SimpleNamespace
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from poetry.services.poem_editor import save_poem
from memorization.models import MemorizationItem, ReviewLog
from memorization.services.scheduler import calculate_next_review
from memorization.services.reviews import rate_item, get_due_items, ReviewConflict
from memorization.services.selections import create_item, get_item_verses

class SchedulerTests(SimpleTestCase):
    def test_examples_and_all_ratings(self):
        now = timezone.now()
        item = SimpleNamespace(interval_days=0, streak=0, lapses=0)
        for rating, days in [('hard', 1), ('good', 1), ('easy', 3)]:
            result = calculate_next_review(item, rating, now)
            self.assertEqual(result['interval_days'], days)
            self.assertEqual(result['due_at'], now + timedelta(days=days))
        for rating, days in [('good', 1), ('good', 2), ('easy', 6), ('again', 0)]:
            result = calculate_next_review(item, rating, now)
            self.assertEqual(result['interval_days'], days)
            for key, value in result.items(): setattr(item, key, value)
        self.assertEqual(item.due_at, now + timedelta(minutes=10))
        self.assertEqual(item.streak, 0)
        self.assertEqual(item.lapses, 1)
        with self.assertRaises(ValueError): calculate_next_review(item, 'invalid', now)
        item.interval_days = 1
        self.assertEqual(calculate_next_review(item, 'hard', now)['interval_days'], 1)

class ReviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('reader')
        data = dict(title='عنوان', poet_name='نمونه', source_url='', notes='', tags=[])
        self.poem = save_poem(self.user, data, [(f'بیت {i}', 'پاسخ') for i in range(30)])
        self.item = create_item(self.user, self.poem, 'full')
        self.client.force_login(self.user)

    def test_full_unlimited_and_duplicate_constraints(self):
        self.assertEqual(get_item_verses(self.item).count(), 30)
        with self.assertRaises(ValidationError): create_item(self.user, self.poem, 'full')
        with self.assertRaises(IntegrityError), transaction.atomic():
            MemorizationItem.objects.create(owner=self.user, poem=self.poem, scope='full')
        with self.assertRaises(IntegrityError), transaction.atomic():
            MemorizationItem.objects.create(owner=self.user, poem=self.poem, scope='range')

    def test_range_validation(self):
        verses = list(self.poem.verses.all())
        item = create_item(self.user, self.poem, 'range', verses[1], verses[4])
        self.assertEqual(get_item_verses(item).count(), 4)
        create_item(self.user, self.poem, 'range', verses[1], verses[1])
        with self.assertRaises(ValidationError): create_item(self.user, self.poem, 'range', verses[4], verses[1])
        with self.assertRaises(ValidationError): create_item(self.user, self.poem, 'range', None, None)
        foreign = save_poem(self.user, dict(title='', poet_name='دیگر', source_url='', notes='', tags=[]), [('الف', '')])
        with self.assertRaises(ValidationError): create_item(self.user, self.poem, 'range', verses[0], foreign.verses.first())

    def test_idempotence_and_not_due(self):
        request_id = uuid.uuid4()
        log = rate_item(self.user, self.item.pk, 'good', request_id)
        again = rate_item(self.user, self.item.pk, 'good', request_id)
        self.assertEqual(log.pk, again.pk)
        self.item.refresh_from_db()
        self.assertEqual(self.item.review_count, 1)
        self.assertEqual(ReviewLog.objects.count(), 1)
        with self.assertRaises(ReviewConflict): rate_item(self.user, self.item.pk, 'good', uuid.uuid4())
        self.assertEqual(get_due_items(self.user).count(), 0)

    def test_rating_endpoint_invalid_and_repeat(self):
        url = f'/review/{self.item.pk}/rate/'
        for data in [{'rating': 'bad', 'request_id': str(uuid.uuid4())}, {'rating': 'good', 'request_id': 'bad'}]:
            self.assertEqual(self.client.post(url, data).status_code, 400)
        payload = {'rating': 'again', 'request_id': str(uuid.uuid4())}
        for _ in range(2): self.assertEqual(self.client.post(url, payload, HTTP_ACCEPT='application/json').status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.review_count, 1)
        self.assertEqual(self.item.lapses, 1)

    def test_pause_resume_confirm_delete(self):
        self.client.post(f'/memorize/items/{self.item.pk}/pause/')
        self.assertEqual(get_due_items(self.user).count(), 0)
        self.client.post(f'/memorize/items/{self.item.pk}/resume/')
        self.assertEqual(get_due_items(self.user).count(), 1)
        self.client.post(f'/memorize/items/{self.item.pk}/delete/')
        self.assertTrue(MemorizationItem.objects.filter(pk=self.item.pk).exists())
        self.client.post(f'/memorize/items/{self.item.pk}/delete/', {'confirm': 'yes'})
        self.assertFalse(MemorizationItem.objects.filter(pk=self.item.pk).exists())
        self.assertTrue(self.poem.verses.exists())

from concurrent.futures import ThreadPoolExecutor
from django.test import TransactionTestCase
from django.db import connections

class ConcurrentReviewTests(TransactionTestCase):
    def test_same_uuid_from_two_connections_records_once(self):
        user = get_user_model().objects.create_user('parallel')
        poem = save_poem(user, dict(title='', poet_name='نمونه', source_url='', notes='', tags=[]), [('اول', 'دوم')])
        item = create_item(user, poem, 'full')
        request_id = uuid.uuid4()
        def rate():
            try:
                return rate_item(user, item.pk, 'good', request_id).pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: rate(), range(2)))
        self.assertEqual(results[0], results[1])
        item.refresh_from_db()
        self.assertEqual(item.review_count, 1)
        self.assertEqual(ReviewLog.objects.count(), 1)

class SelectionHTTPTests(TestCase):
    setUp = ReviewTests.setUp

    def test_range_error_vs_duplicate_status(self):
        verses = list(self.poem.verses.all())
        response = self.client.post('/memorize/items/', {'poem_id': self.poem.pk, 'scope': 'range',
                                   'start_verse_id': verses[2].pk, 'end_verse_id': verses[0].pk}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_range')
        response = self.client.post('/memorize/items/', {'poem_id': self.poem.pk, 'scope': 'full'}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 409)
