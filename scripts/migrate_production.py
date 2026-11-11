"""Run production migrations with a direct PostgreSQL connection."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.environment import migration_database_url

if __name__ == '__main__':
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_production'
    os.environ['DATABASE_URL'] = migration_database_url()
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', 'migrate', '--noinput'])
