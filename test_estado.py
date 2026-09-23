import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.personal.models import OrdenTrabajo, TareaOrdenTrabajo

for o in OrdenTrabajo.objects.all():
    print(f"Orden ID: {o.id}")
    for t in o.tareas.all():
        print(f"  Tarea ID: {t.id} - Estado: {t.estado}")
    todas_completadas = not o.tareas.exclude(estado='COMPLETADA').exists()
    print(f"  todas_completadas: {todas_completadas}")
