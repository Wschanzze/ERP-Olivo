import re

with open('apps/personal/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Modify OrdenTrabajo
new_orden_fields = """    class Estado(models.TextChoices):
        PLANIFICADA = 'PLANIFICADA', _('Planificada')
        EN_CURSO = 'EN_CURSO', _('En Curso')
        COMPLETADA = 'COMPLETADA', _('Completada')
        CANCELADA = 'CANCELADA', _('Cancelada')

    semana_inicio = models.DateField(verbose_name=_("Semana (Inicio)"))
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PLANIFICADA, verbose_name=_("Estado"))"""
content = re.sub(r'semana_inicio = models\.DateField\(verbose_name=_\("Semana \(Inicio\)"\)\)', new_orden_fields, content)

# Modify TareaOrdenTrabajo
new_tarea_fields = """    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', _('Pendiente')
        EN_PROGRESO = 'EN_PROGRESO', _('En Progreso')
        COMPLETADA = 'COMPLETADA', _('Completada')
        CANCELADA = 'CANCELADA', _('Cancelada')

    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='tareas')
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE, verbose_name=_("Estado"))
    cantidad_completada = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name=_("Cantidad Completada"))"""
content = re.sub(r'orden = models\.ForeignKey\(OrdenTrabajo, on_delete=models\.CASCADE, related_name=\'tareas\'\)', new_tarea_fields, content)

with open('apps/personal/models.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Modificados modelos con exito.")
