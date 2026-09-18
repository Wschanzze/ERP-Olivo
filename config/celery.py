import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('erp_olivo')

# Usar configuración de Django prefijada con CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodescubrimiento de tareas en todas las apps instaladas
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
