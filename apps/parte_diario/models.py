from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel, Finca
from apps.campos.models import Cuadro
from apps.personal.models import Empleado
from apps.inventario.models import Insumo, Deposito, MovimientoStock

class OrdenDeTrabajo(TimeStampedModel):
    """Planificación agronómica de labores de campo a ejecutar en los olivares."""
    class TipoLabor(models.TextChoices):
        PODA_FORMACION = 'PODA_FORMACION', _('Poda de Formación')
        PODA_PRODUCCION = 'PODA_PRODUCCION', _('Poda de Producción / Aclareo')
        CURA_FITOSANITARIA = 'CURA_FITOSANITARIA', _('Cura Fitosanitaria (Repilo, Mosca, Cochinilla)')
        FERTIRRIEGO = 'FERTIRRIEGO', _('Fertirriego / Nutrición')
        DESMALEZADO = 'DESMALEZADO', _('Desmalezado Mecánico / Químico')
        MANTENIMIENTO_RIEGO = 'MANTENIMIENTO_RIEGO', _('Mantenimiento y Reparación de Riego')
        COSECHA_MANUAL = 'COSECHA_MANUAL', _('Cosecha Manual')
        COSECHA_MECANICA = 'COSECHA_MECANICA', _('Cosecha Mecanizada (Vibrador)')
        LABOR_SUELO = 'LABOR_SUELO', _('Laboreo de Suelo / Subsolado')
        OTRA = 'OTRA', _('Otra Labor Agrícola')

    class Estado(models.TextChoices):
        PLANIFICADA = 'PLANIFICADA', _('Planificada')
        EN_EJECUCION = 'EN_EJECUCION', _('En Ejecución')
        FINALIZADA = 'FINALIZADA', _('Finalizada')
        CANCELADA = 'CANCELADA', _('Cancelada')

    cuadro = models.ForeignKey(Cuadro, on_delete=models.CASCADE, related_name='ordenes_trabajo', verbose_name=_("Cuadro"))
    tipo_labor = models.CharField(max_length=35, choices=TipoLabor.choices, verbose_name=_("Tipo de Labor"))
    fecha_programada = models.DateField(verbose_name=_("Fecha Programada"))
    fecha_limite = models.DateField(null=True, blank=True, verbose_name=_("Fecha Límite"))
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name=_("Agrónomo / Encargado Responsable")
    )
    instrucciones_tecnicas = models.TextField(
        blank=True, 
        verbose_name=_("Instrucciones Agronómicas"),
        help_text=_("Dosis, calibración de pulverizadora, recomendaciones de seguridad")
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PLANIFICADA, verbose_name=_("Estado"))

    class Meta:
        verbose_name = _("Orden de Trabajo")
        verbose_name_plural = _("Órdenes de Trabajo")
        ordering = ['-fecha_programada']

    def __str__(self):
        return f"OT #{self.id} - {self.get_tipo_labor_display()} ({self.cuadro})"


class ParteDiario(TimeStampedModel):
    """Ejecución real de campo diaria: cuadrillas de trabajo e insumos consumidos."""
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador (En Carga)')
        CONFIRMADO_CERRADO = 'CONFIRMADO_CERRADO', _('Confirmado y Cerrado')

    orden_de_trabajo = models.ForeignKey(
        OrdenDeTrabajo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='partes_diarios', 
        verbose_name=_("Orden de Trabajo (opcional)")
    )
    finca = models.ForeignKey(Finca, on_delete=models.CASCADE, related_name='partes_diarios', verbose_name=_("Finca"))
    cuadro = models.ForeignKey(Cuadro, on_delete=models.CASCADE, related_name='partes_diarios', verbose_name=_("Cuadro / Cuartel"))
    fecha = models.DateField(verbose_name=_("Fecha de Ejecución"))
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='partes_supervisados', 
        verbose_name=_("Encargado / Supervisor")
    )
    estado = models.CharField(max_length=25, choices=Estado.choices, default=Estado.BORRADOR, verbose_name=_("Estado"))
    observaciones = models.TextField(blank=True, verbose_name=_("Novedades de Campo"))
    fecha_cierre = models.DateTimeField(null=True, blank=True, verbose_name=_("Fecha y Hora de Cierre"))

    class Meta:
        verbose_name = _("Parte Diario")
        verbose_name_plural = _("Partes Diarios")
        ordering = ['-fecha', '-created_at']

    def __str__(self):
        return f"Parte #{self.id} - {self.fecha} - {self.cuadro.codigo} ({self.get_estado_display()})"

    @property
    def total_costo_insumos_ars(self):
        return sum(item.costo_total_ars for item in self.insumos_utilizados.all())

    @property
    def total_costo_personal_ars(self):
        return sum(item.costo_jornal_calculado_ars for item in self.personal_asignado.all())

    @property
    def total_costo_parte_ars(self):
        return self.total_costo_insumos_ars + self.total_costo_personal_ars


class ParteDiarioPersonal(TimeStampedModel):
    """Personal y jornales asignados al parte diario."""
    parte_diario = models.ForeignKey(
        ParteDiario, 
        on_delete=models.CASCADE, 
        related_name='personal_asignado', 
        verbose_name=_("Parte Diario")
    )
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, verbose_name=_("Empleado"))
    horas_normales = models.DecimalField(max_digits=4, decimal_places=1, default=8.0, verbose_name=_("Horas Normales"))
    horas_extras = models.DecimalField(max_digits=4, decimal_places=1, default=0.0, verbose_name=_("Horas Extras"))
    tarea_especifica = models.CharField(max_length=100, blank=True, verbose_name=_("Labor Específica"))
    costo_jornal_calculado_ars = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        verbose_name=_("Costo Jornal Imputado (ARS)")
    )

    class Meta:
        verbose_name = _("Personal en Parte Diario")
        verbose_name_plural = _("Personal en Partes Diarios")
        unique_together = ('parte_diario', 'empleado')

    def __str__(self):
        return f"{self.empleado.nombre_completo} ({self.horas_normales}h) en Parte #{self.parte_diario_id}"


class ParteDiarioInsumo(TimeStampedModel):
    """Insumos agrícolas utilizados (agroquímicos, fertilizantes, gasoil)."""
    parte_diario = models.ForeignKey(
        ParteDiario, 
        on_delete=models.CASCADE, 
        related_name='insumos_utilizados', 
        verbose_name=_("Parte Diario")
    )
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, verbose_name=_("Insumo"))
    deposito_origen = models.ForeignKey(Deposito, on_delete=models.PROTECT, verbose_name=_("Depósito de Retiro"))
    cantidad_utilizada = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Cantidad Utilizada"))
    dosis_por_hectarea = models.CharField(max_length=50, blank=True, verbose_name=_("Dosis / Ha"))
    costo_unitario_aplicado_ars = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00, 
        verbose_name=_("Costo Unitario al Cierre (ARS)")
    )
    costo_total_ars = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00, 
        verbose_name=_("Costo Total Insumo (ARS)")
    )
    movimiento_stock_generado = models.ForeignKey(
        MovimientoStock, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name=_("Movimiento de Stock Asociado")
    )

    class Meta:
        verbose_name = _("Insumo Utilizado en Parte")
        verbose_name_plural = _("Insumos Utilizados en Partes")

    def __str__(self):
        return f"{self.insumo.nombre} ({self.cantidad_utilizada} {self.insumo.unidad_medida}) en Parte #{self.parte_diario_id}"
