"""Render/Neon production settings. Never reads the local .env file."""
from django.core.exceptions import ImproperlyConfigured
from .settings_base import *  # noqa: F403
from .environment import boolean, integer, value, production_hosts, production_origins, postgres_database

if boolean('DEBUG', False, legacy='DJANGO_DEBUG'):
    raise ImproperlyConfigured('DEBUG must be false in production.')
DEBUG = False
SECRET_KEY = value('SECRET_KEY', legacy='DJANGO_SECRET_KEY')
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith(('django-insecure-', 'replace-', 'change-me')):
    raise ImproperlyConfigured('A strong SECRET_KEY of at least 50 characters is required in production.')
ALLOWED_HOSTS = production_hosts()
CSRF_TRUSTED_ORIGINS = production_origins()
DATABASES = {'default': postgres_database(value('DATABASE_URL'))}
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
# A public liveness probe without user data; does not keep Neon compute awake.
SECURE_REDIRECT_EXEMPT = [r'^healthz/$']
if boolean('TRUST_PROXY', boolean('RENDER', False)):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# Opt in after the final hostname and HTTPS behavior have been verified.
SECURE_HSTS_SECONDS = integer('SECURE_HSTS_SECONDS', 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = boolean('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = boolean('SECURE_HSTS_PRELOAD', False)
if SECURE_HSTS_PRELOAD and (SECURE_HSTS_SECONDS < 31536000 or not SECURE_HSTS_INCLUDE_SUBDOMAINS):
    raise ImproperlyConfigured('HSTS preload requires at least one year and includeSubDomains; enable only after HTTPS verification.')
LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {'django': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False}},
}
