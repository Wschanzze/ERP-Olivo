import re

with open('apps/parte_diario/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. ADD IMPORT
import_str = "from apps.personal.models import Empleado, OrdenTrabajo, TareaOrdenTrabajo"
content = content.replace("from apps.personal.models import Empleado", import_str)

# 2. MODIFY ParteDiario
old_pd_orden = """    orden_de_trabajo = models.ForeignKey(
        OrdenDeTrabajo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='partes_diarios', 
        verbose_name=_("Orden de Trabajo (opcional)")
    )"""
new_pd_orden = """    orden_trabajo = models.ForeignKey(
        OrdenTrabajo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='partes_diarios', 
        verbose_name=_("Orden de Trabajo Semanal")
    )"""
content = content.replace(old_pd_orden, new_pd_orden)

old_pd_cuadro = """    cuadro = models.ForeignKey(Cuadro, on_delete=models.CASCADE, related_name='partes_diarios', verbose_name=_("Cuadro / Cuartel"))"""
new_pd_cuadro = """    cuadro = models.ForeignKey(Cuadro, on_delete=models.SET_NULL, null=True, blank=True, related_name='partes_diarios', verbose_name=_("Cuadro / Cuartel"))"""
content = content.replace(old_pd_cuadro, new_pd_cuadro)

# 3. ADD AvanceTarea
avance_tarea_model = """

class AvanceTarea(TimeStampedModel):
    \"\"\"Registro de cuánto se avanzó en una tarea planificada de una Orden de Trabajo.\"\"\"
    parte_diario = models.ForeignKey(ParteDiario, on_delete=models.CASCADE, related_name='avances_tareas')
    tarea = models.ForeignKey(TareaOrdenTrabajo, on_delete=models.CASCADE, related_name='avances')
    cantidad_avanzada = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Avance de Tarea")
        verbose_name_plural = _("Avances de Tareas")

    def __str__(self):
        return f"{self.tarea.actividad}: +{self.cantidad_avanzada} en Parte #{self.parte_diario.id}"
"""
content = content + avance_tarea_model

with open('apps/parte_diario/models.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Models refactored!")
