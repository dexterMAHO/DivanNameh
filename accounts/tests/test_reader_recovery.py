from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User


class ReaderRecoveryTests(TestCase):
    def test_recovery_is_one_use_and_revocation_ends_the_bound_session(self):
        first, second, third = Client(), Client(), Client()
        first.post(reverse('signup'), {'username': 'reader'})
        response = first.post(reverse('settings'), {'section': 'recovery'})
        code = response.context['recovery_code']
        user = User.objects.get(username='reader')
        self.assertNotEqual(user.recovery_digest, code)

        self.assertRedirects(second.post(reverse('recover-account'), {'code': code}), reverse('dashboard'))
        self.assertContains(third.post(reverse('recover-account'), {'code': code}), 'کد معتبر نیست')
        settings = first.get(reverse('settings'))
        browser = next(browser for browser in settings.context['browsers'] if not browser.is_current)
        first.post(reverse('settings'), {'section': 'revoke-browser', 'browser_id': browser.pk})
        self.assertRedirects(second.get(reverse('poems')), reverse('login') + '?next=/poems/')
        self.assertEqual(first.get(reverse('poems')).status_code, 200)

    def test_reading_preferences_are_saved_independently_of_palette(self):
        user = User.objects.create_user(username='reader', palette='forest')
        self.client.force_login(user)
        self.assertRedirects(self.client.post(reverse('settings'), {
            'section': 'reading', 'reading_size': 'largest', 'reading_spacing': 'wide',
            'reading_layout': 'stacked',
        }), reverse('settings'))
        user.refresh_from_db()
        self.assertEqual(user.palette, 'forest')
        self.assertEqual(user.reading_size, 'largest')
        self.assertFalse(user.reading_numbers)
