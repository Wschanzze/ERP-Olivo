import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.personal.models import OrdenTrabajo, TareaOrdenTrabajo

tarea = TareaOrdenTrabajo.objects.get(id=2)
nuevo_estado = 'COMPLETADA'

tarea.estado = nuevo_estado
tarea.save()

orden = tarea.orden
todas_completadas = not orden.tareas.exclude(estado='COMPLETADA').exists()

print(f"Despues de marcar tarea 2 como completada:")
print(f"  todas_completadas: {todas_completadas}")

print("Verificando SQL:")
print(orden.tareas.exclude(estado='COMPLETADA').query)
