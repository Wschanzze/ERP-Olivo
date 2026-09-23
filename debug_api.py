import os
import django
import json
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from apps.personal.models import OrdenTrabajo, TareaOrdenTrabajo

# Make sure Order 2 has 1 completada, 1 pendiente
o = OrdenTrabajo.objects.get(id=2)
o.estado = 'PLANIFICADA'
o.save()

t2 = TareaOrdenTrabajo.objects.get(id=2)
t2.estado = 'PENDIENTE'
t2.save()
t3 = TareaOrdenTrabajo.objects.get(id=3)
t3.estado = 'PENDIENTE'
t3.save()

c = Client()
# Change t2 to COMPLETADA
response = c.post('/asistencia/orden-trabajo/estado/', json.dumps({
    'tipo': 'tarea',
    'id': 2,
    'estado': 'COMPLETADA'
}), content_type="application/json")

print(response.content)

o.refresh_from_db()
print(f"Orden 2 Estado tras POST: {o.estado}")
