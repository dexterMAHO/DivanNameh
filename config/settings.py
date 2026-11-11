"""Compatibility entry point; explicit production configuration on Render."""
import os
from django.core.exceptions import ImproperlyConfigured

profile = os.environ.get('DJANGO_ENV', 'development').strip().lower()
if os.environ.get('RENDER', '').lower() == 'true':
    profile = 'production'
if profile == 'production':
    from .settings_production import *  # noqa: F403
elif profile == 'development':
    from .settings_development import *  # noqa: F403
else:
    raise ImproperlyConfigured('DJANGO_ENV must be development or production.')
