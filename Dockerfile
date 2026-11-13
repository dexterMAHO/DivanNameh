FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings_production
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system django \
    && useradd --system --gid django --no-create-home django

COPY . .
RUN SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
    ALLOWED_HOSTS=localhost DATABASE_URL=postgresql://build:build@localhost/build \
    python manage.py collectstatic --noinput

USER django
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
