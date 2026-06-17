import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "telecom_revenue.settings")

app = Celery("telecom_revenue")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
