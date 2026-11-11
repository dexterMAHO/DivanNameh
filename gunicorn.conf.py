"""Conservative starting point for a small Render instance."""
import os

bind = f'0.0.0.0:{os.environ.get("PORT", "8000")}'
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
worker_class = 'sync'
timeout = 60
graceful_timeout = 30
accesslog = '-'
errorlog = '-'
loglevel = 'info'
# Omit query strings, headers and request bodies from access logs.
access_log_format = '%(h)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(B)s %(L)s'
