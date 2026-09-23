import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.personal.models import OrdenTrabajo

orden = OrdenTrabajo.objects.get(id=2)
print(f"Orden ID: {orden.id}")
for t in orden.tareas.all():
    print(f"Tarea: {t.id} - Estado: '{t.estado}'")
    
qs = orden.tareas.exclude(estado='COMPLETADA')
print(f"Exclude COMPLETADA count: {qs.count()}")
print(f"Exists: {qs.exists()}")
