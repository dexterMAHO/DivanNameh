from django.contrib.auth import get_user_model
from django.test import TestCase


class AppearanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('palette-reader')

    def setUp(self):
        self.client.force_login(self.user)

    def test_all_combinations_persist_and_render(self):
        for palette, _ in get_user_model()._meta.get_field('palette').choices:
            for theme in ('auto', 'light', 'dark'):
                with self.subTest(palette=palette, theme=theme):
                    response = self.client.post('/settings/', {
                        'section': 'theme', 'theme': theme, 'palette': palette,
                    }, follow=True)
                    self.user.refresh_from_db()
                    self.assertEqual((self.user.theme, self.user.palette), (theme, palette))
                    self.assertContains(response, f'data-palette="{palette}"')
                    self.assertContains(response, f'data-theme="{theme}"')
                    self.assertContains(self.client.get('/poems/'), f'data-palette="{palette}"')

    def test_invalid_palette_does_not_change_preferences(self):
        response = self.client.post('/settings/', {
            'section': 'theme', 'theme': 'dark', 'palette': 'invalid',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('palette', response.context['theme_form'].errors)
        self.user.refresh_from_db()
        self.assertEqual((self.user.theme, self.user.palette), ('auto', 'paper'))

    def test_header_toggle_preserves_palette_and_safe_redirect(self):
        get_user_model().objects.filter(pk=self.user.pk).update(palette='forest')
        response = self.client.post('/settings/theme/', {
            'theme': 'dark', 'next': 'https://example.org/',
        })
        self.assertRedirects(response, '/')
        self.user.refresh_from_db()
        self.assertEqual((self.user.theme, self.user.palette), ('dark', 'forest'))

    def test_anonymous_cannot_write_preferences(self):
        self.client.logout()
        self.assertEqual(self.client.post('/settings/', {
            'section': 'theme', 'theme': 'dark', 'palette': 'forest',
        }).status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.palette, 'paper')

    def test_settings_get_does_not_validate_unsubmitted_photo(self):
        response = self.client.get('/settings/')
        self.assertFalse(response.context['photo_form'].is_bound)
        self.assertNotContains(response, 'aria-invalid="true"')
