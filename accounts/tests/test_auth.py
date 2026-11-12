from io import BytesIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.access import BROWSER_COOKIE


@override_settings(TURNSTILE_SITE_KEY='', TURNSTILE_SECRET_KEY='')
class AuthTests(TestCase):
    def submit(self, path, username, client=None):
        client = client or self.client
        client.get(path)
        return client.post(path, {'username': username, 'human_answer': client.session['human_answer']})

    def test_signup_and_username_login_in_registered_browser(self):
        self.assertRedirects(self.submit('/signup/', 'reader'), '/')
        user = get_user_model().objects.get(username='reader')
        self.assertFalse(user.has_usable_password())
        self.client.post('/logout/')
        self.assertRedirects(self.submit('/login/', 'reader'), '/')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.client.post('/logout/', {'forget': '1'})
        self.assertContains(self.submit('/login/', 'reader'), 'ورود با این مرورگر ممکن نیست')

    def test_unknown_browser_and_missing_challenge_cannot_login(self):
        self.submit('/signup/', 'reader')
        stranger = Client()
        self.assertContains(self.submit('/login/', 'reader', stranger), 'ورود با این مرورگر ممکن نیست')
        self.assertNotIn('_auth_user_id', stranger.session)
        response = stranger.post('/signup/', {'username': 'bot'})
        self.assertContains(response, 'تأیید انسان بودن انجام نشد')
        self.assertFalse(get_user_model().objects.filter(username='bot').exists())

    def test_two_browsers_can_sign_in_and_be_revoked_independently(self):
        self.assertRedirects(self.submit('/signup/', 'reader'), '/')
        link_response = self.client.post('/settings/', {'section': 'browser-link'})
        url = urlsplit(link_response.context['browser_link'])
        token = parse_qs(url.query)['token'][0]
        other = Client()
        self.assertRedirects(other.post(url.path, {'token': token}), '/')
        self.assertContains(Client().post(url.path, {'token': token}), 'پیوند معتبر نیست')

        for browser in (self.client, other):
            browser.post('/logout/')
            self.assertRedirects(self.submit('/login/', 'reader', browser), '/')

        revoked_cookie = other.cookies[BROWSER_COOKIE].value
        other.post('/logout/', {'forget': '1'})
        other.cookies[BROWSER_COOKIE] = revoked_cookie
        self.assertContains(self.submit('/login/', 'reader', other), 'ورود با این مرورگر ممکن نیست')
        self.client.post('/logout/')
        self.assertRedirects(self.submit('/login/', 'reader'), '/')

    def test_admin_login_and_one_time_link_for_existing_reader(self):
        model = get_user_model()
        admin = model.objects.create_superuser('admin-test', password='admin-test-secret-7712')
        user = model.objects.create_user('existing-reader', password='old-reader-password')
        self.assertContains(self.submit('/login/', admin.username), 'ورود با این مرورگر ممکن نیست')
        index = reverse('admin:index')
        self.assertRedirects(self.client.post(reverse('admin:login'), {
            'username': admin.username, 'password': 'admin-test-secret-7712', 'next': index,
        }), index)
        changelist = reverse('admin:accounts_user_changelist')
        response = self.client.post(changelist, {'action': 'create_reader_link', '_selected_action': [user.pk]}, follow=True)
        link = next(str(message) for message in response.context['messages'] if 'پیوند ثبت مرورگر' in str(message))
        url = urlsplit(link.split('href="', 1)[1].split('"', 1)[0])
        browser = Client()
        self.assertContains(browser.get(f'{url.path}?{url.query}'), 'ثبت مرورگر')
        token = parse_qs(url.query)['token'][0]
        result = browser.post(url.path, {'token': token})
        self.assertRedirects(result, '/')
        self.assertTrue(result.cookies[BROWSER_COOKIE]['httponly'])
        self.assertEqual(int(browser.session['_auth_user_id']), user.pk)
        self.assertContains(Client().post(url.path, {'token': token}), 'پیوند معتبر نیست')

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

    def test_many_pending_links_and_sessions_are_independent(self):
        self.submit('/signup/', 'reader')
        tokens = []
        for _ in range(8):
            response = self.client.post('/settings/', {'section': 'browser-link'})
            tokens.append(parse_qs(urlsplit(response.context['browser_link']).query)['token'][0])
        browsers = [self.client]
        for token in tokens:
            browser = Client()
            self.assertRedirects(browser.post('/login/confirm/', {'token': token}), '/')
            browsers.append(browser)
            self.assertContains(Client().post('/login/confirm/', {'token': token}), 'پیوند معتبر نیست')
        self.assertEqual(get_user_model().objects.get(username='reader').trusted_browsers.count(), 9)
        browsers[1].post('/logout/', {'forget': '1'})
        for browser in [browsers[0], *browsers[2:]]:
            self.assertEqual(browser.get('/settings/').status_code, 200)
            browser.post('/logout/')
            self.assertRedirects(self.submit('/login/', 'reader', browser), '/')

    def test_expired_link_cannot_enroll_browser(self):
        from datetime import timedelta
        from django.utils import timezone
        from accounts.models import BrowserAccessLink
        self.submit('/signup/', 'reader')
        response = self.client.post('/settings/', {'section': 'browser-link'})
        token = parse_qs(urlsplit(response.context['browser_link']).query)['token'][0]
        BrowserAccessLink.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        browser = Client()
        self.assertContains(browser.post('/login/confirm/', {'token': token}), 'پیوند معتبر نیست')
        self.assertNotIn('_auth_user_id', browser.session)

    def test_legacy_link_survives_new_link_creation(self):
        from datetime import timedelta
        from django.utils import timezone
        from accounts.access import digest
        self.submit('/signup/', 'reader')
        get_user_model().objects.filter(username='reader').update(
            access_link_hash=digest('legacy-token'),
            access_link_expires_at=timezone.now() + timedelta(minutes=10),
        )
        self.client.post('/settings/', {'section': 'browser-link'})
        self.assertRedirects(Client().post('/login/confirm/', {'token': 'legacy-token'}), '/')
        self.assertContains(Client().post('/login/confirm/', {'token': 'legacy-token'}), 'پیوند معتبر نیست')
