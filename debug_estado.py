import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.personal.models import OrdenTrabajo

o = OrdenTrabajo.objects.get(id=2)
print(f"Orden 2 Estado: {o.estado}")
