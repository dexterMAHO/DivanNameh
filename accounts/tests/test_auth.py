from django.contrib.auth import get_user_model
from django.test import TestCase

class AuthTests(TestCase):
    def test_login_logout_and_no_registration(self):
        get_user_model().objects.create_user('reader', password='strong-test-314159')
        response = self.client.post('/login/', {'username': 'reader', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post('/login/', {'username': 'reader', 'password': 'strong-test-314159'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)
        self.client.post('/logout/')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.get('/register/').status_code, 404)
