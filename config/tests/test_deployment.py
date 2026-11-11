"""Configuration tests use fake URLs and never connect to a real service."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from config.environment import migration_database_url, postgres_database

ROOT = Path(__file__).resolve().parents[2]


class ProductionSettingsTests(SimpleTestCase):
    def inspect(self, changes=None, remove=(), module='config.settings_production'):
        env = {key: val for key, val in os.environ.items() if not key.startswith(('DJANGO_', 'RENDER', 'SECURE_', 'CSRF_')) and key not in {
            'SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS', 'DATABASE_URL', 'DATABASE_MIGRATION_URL', 'TRUST_PROXY', 'DB_CONN_MAX_AGE'}}
        env.update(DJANGO_SETTINGS_MODULE=module, DJANGO_READ_DOTENV='False')
        if module != 'config.settings_development':
            env.update(SECRET_KEY=secrets.token_urlsafe(64), DEBUG='False', RENDER='true',
                       RENDER_EXTERNAL_HOSTNAME='divannameh-test.onrender.com',
                       DATABASE_URL='postgresql://test_role:unused@ep-example.neon.tech/test_db?sslmode=require')
        env.update(changes or {})
        for key in remove:
            env.pop(key, None)
        code = '''from django.conf import settings as s
import json
print(json.dumps({'debug':s.DEBUG,'engine':s.DATABASES['default']['ENGINE'],'hosts':s.ALLOWED_HOSTS,
'origins':s.CSRF_TRUSTED_ORIGINS,'ssl':s.DATABASES['default'].get('OPTIONS',{}).get('sslmode'),
'age':s.DATABASES['default']['CONN_MAX_AGE'],'health':s.DATABASES['default'].get('CONN_HEALTH_CHECKS'),
'proxy':getattr(s,'SECURE_PROXY_SSL_HEADER',None),'cookies':s.SESSION_COOKIE_SECURE,
'storage':s.STORAGES['staticfiles']['BACKEND'],'hsts':s.SECURE_HSTS_SECONDS}))'''
        return subprocess.run([sys.executable, '-c', code], env=env, cwd=ROOT, capture_output=True, text=True)

    def test_render_production_defaults(self):
        result = self.inspect(module='config.settings')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data['debug'])
        self.assertEqual(data['engine'], 'django.db.backends.postgresql')
        self.assertEqual(data['hosts'], ['divannameh-test.onrender.com'])
        self.assertEqual(data['origins'], ['https://divannameh-test.onrender.com'])
        self.assertEqual(data['proxy'], ['HTTP_X_FORWARDED_PROTO', 'https'])
        self.assertTrue(data['cookies'])
        self.assertEqual(data['age'], 0)
        self.assertTrue(data['health'])
        self.assertEqual(data['ssl'], 'require')
        self.assertIn('CompressedManifest', data['storage'])
        self.assertEqual(data['hsts'], 0)

    def test_custom_domains_merge_and_trim(self):
        result = self.inspect({'ALLOWED_HOSTS': 'poems.example.com, ,divannameh-test.onrender.com',
                               'CSRF_TRUSTED_ORIGINS': ' https://poems.example.com, '})
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data['hosts']), 2)
        self.assertIn('https://poems.example.com', data['origins'])

    def test_fail_closed_for_missing_or_unsafe_configuration(self):
        for changes, remove, message in [
            ({}, ['SECRET_KEY'], 'SECRET_KEY'),
            ({'SECRET_KEY': 'replace-with-a-generated-secret'}, [], 'SECRET_KEY'),
            ({'DEBUG': 'True'}, [], 'DEBUG'),
            ({}, ['DATABASE_URL'], 'DATABASE_URL'),
            ({'DATABASE_URL': 'sqlite:///db.sqlite3'}, [], 'PostgreSQL'),
            ({'DATABASE_URL': 'postgresql://user:never-print-this@host/db?sslmode=disable'}, [], 'SSL'),
            ({'ALLOWED_HOSTS': '*'}, [], 'ALLOWED_HOSTS'),
            ({'CSRF_TRUSTED_ORIGINS': 'http://example.com'}, [], 'HTTPS'),
            ({'SECURE_HSTS_PRELOAD': 'True'}, [], 'HSTS'),
        ]:
            with self.subTest(message=message, changes=list(changes)):
                result = self.inspect(changes, remove)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertNotIn('never-print-this', result.stderr)

    def test_development_works_without_database_url_or_env_file(self):
        result = self.inspect(module='config.settings_development')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data['debug'])
        self.assertEqual(data['engine'], 'django.db.backends.sqlite3')
        self.assertFalse(data['cookies'])
        self.assertIsNone(data['proxy'])

    def test_pooled_runtime_direct_migrations(self):
        pooled = 'postgresql://role:unused@ep-example-pooler.neon.tech/app?sslmode=require'
        direct = 'postgresql://role:unused@ep-example.neon.tech/app?sslmode=verify-full'
        with patch.dict(os.environ, {'DATABASE_URL': pooled, 'DATABASE_MIGRATION_URL': ''}):
            db = postgres_database(pooled)
            self.assertIsNone(db['OPTIONS']['prepare_threshold'])
            self.assertTrue(db['DISABLE_SERVER_SIDE_CURSORS'])
            with self.assertRaises(ImproperlyConfigured):
                migration_database_url()
            with patch.dict(os.environ, {'DATABASE_MIGRATION_URL': direct}):
                self.assertEqual(migration_database_url(), direct)
                self.assertEqual(postgres_database(direct)['OPTIONS']['sslmode'], 'verify-full')

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
                       SECURE_REDIRECT_EXEMPT=[r'^healthz/$'])
    def test_health_proxy_and_redirect(self):
        response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertEqual(self.client.post('/healthz/').status_code, 405)
        self.assertEqual(self.client.get('/login/').status_code, 301)
        self.assertEqual(self.client.get('/login/', HTTP_X_FORWARDED_PROTO='https').status_code, 200)
