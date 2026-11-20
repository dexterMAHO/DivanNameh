from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.db import IntegrityError
from django.urls import reverse


@override_settings(READER_HUMAN_CHECK_ENABLED=True, TURNSTILE_SITE_KEY='', TURNSTILE_SECRET_KEY='')
class AuthTests(TestCase):
    def submit(self, path, username, client=None):
        client = client or self.client
        client.get(path)
        return client.post(path, {'username': username, 'human_answer': client.session['human_answer']})

    def test_reader_can_login_with_username_on_a_fresh_browser(self):
        self.assertRedirects(self.submit('/signup/', 'reader'), '/')
        user = get_user_model().objects.get(username='reader')
        self.assertFalse(user.has_usable_password())
        self.client.post('/logout/')
        for browser in (Client(), Client()):
            self.assertRedirects(self.submit('/login/', 'reader', browser), '/')
            self.assertEqual(int(browser.session['_auth_user_id']), user.pk)
            self.assertNotIn('divannameh_reader_browser', browser.cookies)

    def test_unknown_username_and_missing_challenge_cannot_login(self):
        self.assertContains(self.submit('/login/', 'unknown'), 'ورود با این نام کاربری ممکن نیست')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(self.client.post('/signup/', {'username': 'bot'}), 'تأیید انسان بودن انجام نشد')
        self.assertFalse(get_user_model().objects.filter(username='bot').exists())

    def test_staff_superusers_and_inactive_readers_cannot_login_with_username(self):
        model = get_user_model()
        admin = model.objects.create_superuser('admin-test', password='admin-test-secret-7712')
        model.objects.create_user('staff', is_staff=True)
        model.objects.create_user('inactive', is_active=False)
        for username in (admin.username, 'staff', 'inactive'):
            with self.subTest(username=username):
                self.assertContains(self.submit('/login/', username), 'ورود با این نام کاربری ممکن نیست')
                self.assertNotIn('_auth_user_id', self.client.session)
        index = reverse('admin:index')
        self.assertRedirects(self.client.post(reverse('admin:login'), {
            'username': admin.username, 'password': 'admin-test-secret-7712', 'next': index,
        }), index)

    def test_old_session_does_not_depend_on_registered_browser(self):
        user = get_user_model().objects.create_user('legacy-reader')
        self.client.force_login(user)
        session = self.client.session
        session['reader_trusted_browser'] = 999
        session.save()
        self.assertEqual(self.client.get('/settings/').status_code, 200)

    @override_settings(TURNSTILE_SITE_KEY='site-key', TURNSTILE_SECRET_KEY='secret-key')
    def test_turnstile_response_is_validated_on_server(self):
        self.assertContains(self.client.get('/signup/'), 'cf-turnstile')
        self.assertContains(self.client.post('/signup/', {'username': 'reader'}), 'تأیید انسان بودن انجام نشد')
        with patch('accounts.access.urlopen') as call:
            call.return_value.__enter__.return_value = BytesIO(
                b'{"success":true,"action":"reader-access","hostname":"testserver"}'
            )
            self.assertRedirects(self.client.post('/signup/', {
                'username': 'reader', 'cf-turnstile-response': 'example-token',
            }), '/')
            self.assertEqual(call.call_args.args[0].full_url, 'https://challenges.cloudflare.com/turnstile/v0/siteverify')


@override_settings(READER_HUMAN_CHECK_ENABLED=False,
                   TURNSTILE_SITE_KEY='configured-site', TURNSTILE_SECRET_KEY='configured-secret')
class DisabledHumanCheckTests(TestCase):
    def test_pages_do_not_render_or_generate_challenges(self):
        for path in ('/login/', '/signup/'):
            response = self.client.get(path)
            self.assertNotContains(response, 'cf-turnstile')
            self.assertNotContains(response, 'name="human_answer"')
            self.assertNotContains(response, 'challenges.cloudflare.com')
            self.assertNotIn('human_answer', self.client.session)

    @patch('accounts.access.urlopen')
    def test_signup_and_username_login_need_no_challenge(self, verify):
        self.assertRedirects(self.client.post('/signup/', {'username': 'reader'}), '/')
        self.client.post('/logout/')
        self.assertRedirects(self.client.post('/login/', {'username': 'reader'}), '/')
        verify.assert_not_called()
        stranger = Client()
        self.assertRedirects(stranger.post('/login/', {'username': 'reader'}), '/')


@override_settings(READER_HUMAN_CHECK_ENABLED=False)
class SignupErrorTests(TestCase):
    def test_existing_name_has_actionable_error_and_does_not_login(self):
        get_user_model().objects.create_user(username='existing-reader')
        response = self.client.post('/signup/', {'username': 'existing-reader'})
        self.assertContains(response, 'قبلاً ثبت شده است')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(get_user_model().objects.filter(username='existing-reader').count(), 1)

    @patch('accounts.access.User.objects.create', side_effect=IntegrityError('unrelated constraint'))
    def test_other_integrity_failure_is_not_reported_as_username_collision(self, create):
        with self.assertLogs('accounts.access', level='ERROR') as logs:
            response = self.client.post('/signup/', {'username': 'new-reader'})
        self.assertContains(response, 'مشکل ذخیره‌سازی')
        self.assertNotContains(response, 'نام کاربری در دسترس نیست')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn('new-reader', ''.join(logs.output))

    def test_new_name_succeeds_when_other_accounts_already_exist(self):
        get_user_model().objects.create_user(username='first-reader')
        response = self.client.post('/signup/', {'username': 'second-reader'})
        self.assertRedirects(response, '/')
        self.assertEqual(get_user_model().objects.count(), 2)
