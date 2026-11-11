import re
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(PASSWORDLESS_LOGIN=True)
class AuthTests(TestCase):
    def test_verified_email_creates_reader_and_token_cannot_be_reused(self):
        response = self.client.post('/signup/', {'email': 'Reader@example.com'})
        self.assertContains(response, 'صندوق ایمیل')
        self.assertFalse(get_user_model().objects.exists())
        link = re.search(r'https?://\S+', mail.outbox[0].body).group()
        url = urlsplit(link)
        self.assertContains(self.client.get(f'{url.path}?{url.query}'), 'تأیید ورود')
        self.assertFalse(get_user_model().objects.exists())
        token = parse_qs(url.query)['token'][0]
        self.assertRedirects(self.client.post(url.path, {'token': token}), '/')
        user = get_user_model().objects.get(login_email='reader@example.com')
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        self.client.post('/logout/')
        self.assertContains(self.client.post(url.path, {'token': token}), 'پیوند ورود معتبر نیست')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_reader_login_rejects_password_and_admin_has_separate_login(self):
        admin = get_user_model().objects.create_superuser('admin-test', password='admin-test-secret-7712')
        data = {'username': admin.username, 'password': 'admin-test-secret-7712'}
        self.assertEqual(self.client.post('/login/', data).status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        index = reverse('admin:index')
        self.assertRedirects(self.client.post(reverse('admin:login'), {**data, 'next': index}), index)
