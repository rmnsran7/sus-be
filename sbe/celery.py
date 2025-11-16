# /sbe/celery.py

import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sbe.settings')

# Create a Celery instance and configure it using the settings from Django
app = Celery('sbe')

# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all of your applications.
app.autodiscover_tasks()