"""Local development: optional .env, SQLite by default."""
import dj_database_url
from dotenv import load_dotenv
from .settings_base import *  # noqa: F403
from .environment import boolean, csv, value

if boolean('DJANGO_READ_DOTENV', True):
    load_dotenv(BASE_DIR / '.env', override=False)
TURNSTILE_SITE_KEY = value('TURNSTILE_SITE_KEY')
TURNSTILE_SECRET_KEY = value('TURNSTILE_SECRET_KEY')
DEBUG = boolean('DEBUG', True, legacy='DJANGO_DEBUG')
SECRET_KEY = value('SECRET_KEY', 'django-insecure-local-development-only-never-use-in-production', legacy='DJANGO_SECRET_KEY')
ALLOWED_HOSTS = csv('ALLOWED_HOSTS', '127.0.0.1,localhost', legacy='DJANGO_ALLOWED_HOSTS')
CSRF_TRUSTED_ORIGINS = csv('CSRF_TRUSTED_ORIGINS')
DATABASES = {'default': dj_database_url.parse(value('DATABASE_URL') or f'sqlite:///{BASE_DIR / "db.sqlite3"}', conn_max_age=0)}
if DATABASES['default']['ENGINE'].endswith('sqlite3'):
    DATABASES['default']['OPTIONS'] = {'timeout': 20, 'transaction_mode': 'IMMEDIATE'}
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
