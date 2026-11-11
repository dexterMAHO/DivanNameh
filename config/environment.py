"""Small environment parsers shared by the settings profiles."""
import os
from urllib.parse import urlsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


def value(name, default='', legacy=None):
    return os.environ.get(name, os.environ.get(legacy, default) if legacy else default).strip()


def boolean(name, default=False, legacy=None):
    raw = value(name, str(default), legacy).lower()
    if raw not in {'true', 'false', '1', '0'}:
        raise ImproperlyConfigured(f'{name} must be true or false.')
    return raw in {'true', '1'}


def integer(name, default, minimum=0):
    try:
        number = int(value(name, str(default)))
    except ValueError:
        raise ImproperlyConfigured(f'{name} must be an integer.') from None
    if number < minimum:
        raise ImproperlyConfigured(f'{name} must be at least {minimum}.')
    return number


def csv(name, default='', legacy=None):
    return [part.strip() for part in value(name, default, legacy).split(',') if part.strip()]


def production_hosts():
    hosts = csv('ALLOWED_HOSTS', legacy='DJANGO_ALLOWED_HOSTS')
    render_host = value('RENDER_EXTERNAL_HOSTNAME')
    if render_host:
        hosts.append(render_host)
    hosts = list(dict.fromkeys(hosts))
    if not hosts or any('*' in h or '/' in h or ':' in h or h.startswith('.') for h in hosts):
        raise ImproperlyConfigured('ALLOWED_HOSTS must contain explicit hostnames without scheme, port or wildcard.')
    return hosts


def production_origins():
    origins = csv('CSRF_TRUSTED_ORIGINS')
    render_host = value('RENDER_EXTERNAL_HOSTNAME')
    if render_host:
        origins.append(f'https://{render_host}')
    for origin in origins:
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.path or parsed.query or
                parsed.fragment or parsed.username or '*' in origin):
            raise ImproperlyConfigured('CSRF_TRUSTED_ORIGINS must contain explicit HTTPS origins without paths.')
    return list(dict.fromkeys(origins))


def postgres_database(url):
    if not url:
        raise ImproperlyConfigured('DATABASE_URL is required in production; SQLite fallback is disabled.')
    try:
        database = dj_database_url.parse(url, conn_max_age=integer('DB_CONN_MAX_AGE', 0), conn_health_checks=True)
    except (ValueError, KeyError):
        raise ImproperlyConfigured('DATABASE_URL must be a valid PostgreSQL connection URL.') from None
    if database['ENGINE'] != 'django.db.backends.postgresql':
        raise ImproperlyConfigured('Production requires a PostgreSQL DATABASE_URL.')
    if not database.get('HOST') or not database.get('NAME') or not database.get('USER'):
        raise ImproperlyConfigured('DATABASE_URL must include a host, database and role.')
    options = database.setdefault('OPTIONS', {})
    sslmode = options.setdefault('sslmode', 'require')
    if sslmode not in {'require', 'verify-ca', 'verify-full'}:
        raise ImproperlyConfigured('PostgreSQL SSL is required; sslmode must be require, verify-ca or verify-full.')
    options.setdefault('connect_timeout', 10)
    # Transaction pooling and server-side cursors do not share session state.
    database['DISABLE_SERVER_SIDE_CURSORS'] = True
    if '-pooler' in database['HOST']:
        options['prepare_threshold'] = None
    return database


def migration_database_url():
    url = value('DATABASE_MIGRATION_URL') or value('DATABASE_URL')
    database = postgres_database(url)
    if '-pooler' in database['HOST']:
        raise ImproperlyConfigured('Set DATABASE_MIGRATION_URL to the direct Neon connection (without -pooler).')
    return url
