import os

BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

