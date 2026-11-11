"""Explicit local administration of Neon; credentials remain in an ignored file.

Example: python scripts/neon_manage.py --env-file .env.neon check --deploy
This script does not run unless explicitly invoked by the operator.
"""
import argparse
import os
import sys
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.environment import migration_database_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('command', choices=['check', 'showmigrations', 'migrate', 'createsuperuser', 'import_library'])
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.env_file.is_file():
        parser.error('Environment file does not exist.')
    if args.env_file.stat().st_mode & 0o077:
        parser.error('Environment file must be private: chmod 600 <file>.')
    for key, val in dotenv_values(args.env_file).items():
        if val is not None:
            os.environ[key] = val
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_production'
    os.environ['DATABASE_URL'] = migration_database_url()
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', args.command, *args.arguments])


if __name__ == '__main__':
    main()
