from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from memorization.models import MemorizationItem
from poetry.models import OperationRequest, Poem, PoemEditRequest, Verse
from poetry.services.operation_requests import decide_operation


class OperationRequestTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('operations', action_password=make_password('operation-test'))
        self.admin = get_user_model().objects.create_superuser('operation-admin', password='admin-test')
        self.poem = Poem.objects.create(owner=self.user, title='متن', poet_name='شاعر')
        Verse.objects.create(poem=self.poem, position=1, hemistich_1='یک', hemistich_2='دو')
        self.client.force_login(self.user)

    def test_memorization_waits_for_admin_and_does_not_store_password(self):
        data = {'poem_id': self.poem.pk, 'scope': 'full', 'operation_mode': 'request', 'action_password': 'never-store'}
        for _ in range(2):
            response = self.client.post(reverse('item-new'), data, HTTP_ACCEPT='application/json')
            self.assertTrue(response.json()['pending_approval'])
        operation = OperationRequest.objects.get()
        self.assertNotIn('action_password', operation.payload)
        self.assertFalse(MemorizationItem.objects.exists())
        with self.assertRaises(ValidationError):
            decide_operation(operation.pk, self.user, approve=True)
        decide_operation(operation.pk, self.admin, approve=True)
        self.assertEqual(MemorizationItem.objects.get().owner, self.user)
        operation.refresh_from_db()
        self.assertEqual(operation.status, 'approved')
        with self.assertRaises(ValidationError):
            decide_operation(operation.pk, self.admin, approve=True)

    def test_archive_rejection_and_permission_revalidation(self):
        url = reverse('poem-archive', args=[self.poem.pk])
        self.client.post(url, {'operation_mode': 'request'})
        self.poem.refresh_from_db()
        self.assertIsNone(self.poem.archived_at)
        operation = OperationRequest.objects.get()
        decide_operation(operation.pk, self.admin, approve=False)
        self.poem.refresh_from_db()
        self.assertIsNone(self.poem.archived_at)
        self.client.post(url, {'operation_mode': 'request'})
        operation = OperationRequest.objects.get(status='pending')
        self.poem.owner = self.admin
        self.poem.save()
        with self.assertRaises(ValidationError):
            decide_operation(operation.pk, self.admin, approve=True)
        operation.refresh_from_db()
        self.assertEqual(operation.status, 'pending')

    def test_edit_uses_existing_review_queue_and_password_still_required_for_direct(self):
        url = reverse('poem-edit', args=[self.poem.pk])
        data = {'title': 'تازه', 'poet_name': 'شاعر', 'input_mode': 'lines', 'bulk_text': 'اول | دوم'}
        self.client.post(url, data)
        self.assertFalse(PoemEditRequest.objects.exists())
        self.client.post(url, {**data, 'operation_mode': 'request'})
        self.assertEqual(PoemEditRequest.objects.get().status, 'pending')
        self.assertFalse(OperationRequest.objects.exists())
        self.poem.refresh_from_db()
        self.assertEqual(self.poem.title, 'متن')

    def test_staff_cannot_review_operations(self):
        self.user.is_staff = True
        self.user.save()
        self.client.post(reverse('item-new'), {'poem_id': self.poem.pk, 'scope': 'full', 'operation_mode': 'request'})
        self.assertEqual(self.client.get(reverse('admin:poetry_operationrequest_changelist')).status_code, 403)

    def test_archive_can_be_approved_for_reader_without_password(self):
        self.user.action_password = ''
        self.user.save(update_fields=['action_password'])
        self.client.post(reverse('poem-archive', args=[self.poem.pk]), {'operation_mode': 'request'})
        decide_operation(OperationRequest.objects.get().pk, self.admin, approve=True)
        self.poem.refresh_from_db()
        self.assertIsNotNone(self.poem.archived_at)

    def test_arbitrary_replays_cannot_execute(self):
        operation = OperationRequest.objects.create(owner=self.user, path=reverse('poem-restore', args=[self.poem.pk]), payload={}, label='invalid')
        with self.assertRaises(ValidationError):
            decide_operation(operation.pk, self.admin, approve=True)
