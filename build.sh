#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export DJANGO_SETTINGS_MODULE=config.settings_production
python -m pip install -r requirements.txt
python manage.py check
python manage.py collectstatic --noinput
python scripts/migrate_production.py
