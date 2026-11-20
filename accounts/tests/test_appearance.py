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
        self.assertEqual((self.user.theme, self.user.palette), ('auto', 'museum'))

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
        self.assertEqual(self.user.palette, 'museum')

    def test_settings_get_does_not_validate_unsubmitted_photo(self):
        response = self.client.get('/settings/')
        self.assertFalse(response.context['photo_form'].is_bound)
        self.assertNotContains(response, 'aria-invalid="true"')

    def test_custom_palette_persists_across_pages_and_header_toggle(self):
        response = self.client.post('/settings/', {
            'section': 'theme', 'theme': 'auto', 'palette': 'custom',
            'custom_primary': '#AA3366', 'custom_accent': '#225577',
        }, follow=True)
        self.user.refresh_from_db()
        self.assertEqual((self.user.palette, self.user.custom_primary, self.user.custom_accent), ('custom', '#aa3366', '#225577'))
        self.assertContains(response, 'data-custom-primary="#aa3366"')
        self.assertContains(self.client.get('/poems/'), 'data-custom-accent="#225577"')
        self.client.post('/settings/theme/', {'theme': 'dark'})
        self.user.refresh_from_db()
        self.assertEqual((self.user.palette, self.user.custom_primary, self.user.custom_accent), ('custom', '#aa3366', '#225577'))

    def test_custom_colors_reject_invalid_values_without_partial_save(self):
        for color in ('red', '#fff', '" style="color:red', '#12zz34'):
            with self.subTest(color=color):
                response = self.client.post('/settings/', {
                    'section': 'theme', 'theme': 'dark', 'palette': 'custom',
                    'custom_primary': color, 'custom_accent': '#123456',
                })
                self.assertIn('custom_primary', response.context['theme_form'].errors)
                self.user.refresh_from_db()
                self.assertEqual((self.user.palette, self.user.theme), ('museum', 'auto'))

    def test_ready_palette_retains_previously_selected_custom_colors(self):
        get_user_model().objects.filter(pk=self.user.pk).update(custom_primary='#abcdef', custom_accent='#123456')
        self.client.post('/settings/', {'section': 'theme', 'theme': 'light', 'palette': 'ocean'})
        self.user.refresh_from_db()
        self.assertEqual((self.user.custom_primary, self.user.custom_accent), ('#abcdef', '#123456'))
