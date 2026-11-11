from django.contrib.auth import get_user_model
from django.test import TestCase

class AuthTests(TestCase):
    def test_login_logout(self):
        get_user_model().objects.create_user('reader', password='strong-test-314159')
        response = self.client.post('/login/', {'username': 'reader', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post('/login/', {'username': 'reader', 'password': 'strong-test-314159'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)
        self.client.post('/logout/')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_signup_creates_account_and_logs_in(self):
        response = self.client.post('/signup/', {'username': 'newreader', 'password1': 'strong-test-314159', 'password2': 'strong-test-314159'})
        self.assertRedirects(response, '/')
        self.assertIn('_auth_user_id', self.client.session)
        self.assertTrue(get_user_model().objects.filter(username='newreader').exists())

    def test_signup_rejects_mismatched_passwords(self):
        response = self.client.post('/signup/', {'username': 'newreader', 'password1': 'strong-test-314159', 'password2': 'different-521718'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'دو رمز واردشده یکسان نیستند.')
        self.assertFalse(get_user_model().objects.filter(username='newreader').exists())

    def test_signup_redirects_authenticated_users(self):
        get_user_model().objects.create_user('reader', password='strong-test-314159')
        self.client.post('/login/', {'username': 'reader', 'password': 'strong-test-314159'})
        self.assertRedirects(self.client.get('/signup/'), '/')
