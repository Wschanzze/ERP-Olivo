from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel
from apps.personal.models import Empleado

class PeriodoLiquidacion(TimeStampedModel):
    """Período quincenal o mensual de liquidación de haberes para personal agrario."""
    class TipoPeriodo(models.TextChoices):
        PRIMERA_QUINCENA = '1Q', _('1ra Quincena (Días 1 al 15)')
        SEGUNDA_QUINCENA = '2Q', _('2da Quincena (Días 16 a fin de mes)')
        MENSUAL = 'M', _('Mes Completo')

    class Estado(models.TextChoices):
        ABIERTO = 'ABIERTO', _('Abierto para Novedades')
        PROCESANDO = 'PROCESANDO', _('Procesando en Celery...')
        CALCULADO = 'CALCULADO', _('Calculado / En Revisión')
        CERRADO = 'CERRADO', _('Cerrado y Liquidado')

    mes = models.PositiveSmallIntegerField(verbose_name=_("Mes (1-12)"))
    ano = models.PositiveSmallIntegerField(verbose_name=_("Año"))
    tipo = models.CharField(max_length=5, choices=TipoPeriodo.choices, default=TipoPeriodo.PRIMERA_QUINCENA, verbose_name=_("Tipo de Período"))
    fecha_inicio = models.DateField(verbose_name=_("Fecha de Inicio"))
    fecha_fin = models.DateField(verbose_name=_("Fecha de Cierre"))
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABIERTO, verbose_name=_("Estado"))
    observaciones = models.CharField(max_length=200, blank=True, verbose_name=_("Observaciones"))

    class Meta:
        verbose_name = _("Período de Liquidación")
        verbose_name_plural = _("Períodos de Liquidación")
        unique_together = ('mes', 'ano', 'tipo')
        ordering = ['-ano', '-mes', '-tipo']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.mes:02d}/{self.ano} ({self.get_estado_display()})"


class LiquidacionEmpleado(TimeStampedModel):
    """Recibo y cálculo consolidado de haberes para un empleado en un período."""
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador')
        CALCULADO = 'CALCULADO', _('Calculado')
        APROBADO = 'APROBADO', _('Aprobado')
        PAGADO = 'PAGADO', _('Pagado')

    periodo = models.ForeignKey(
        PeriodoLiquidacion, 
        on_delete=models.CASCADE, 
        related_name='liquidaciones', 
        verbose_name=_("Período")
    )
    empleado = models.ForeignKey(
        Empleado, 
        on_delete=models.PROTECT, 
        related_name='liquidaciones', 
        verbose_name=_("Empleado")
    )
    dias_jornales_computados = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00, 
        verbose_name=_("Días/Jornales Computados (Asistencia)")
    )
    horas_normales = models.DecimalField(max_digits=6, decimal_places=1, default=0.0, verbose_name=_("Horas Normales"))
    horas_extras = models.DecimalField(max_digits=6, decimal_places=1, default=0.0, verbose_name=_("Horas Extras"))
    total_bruto_remunerativo_ars = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Total Bruto Remunerativo"))
    total_no_remunerativo_ars = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Total No Remunerativo"))
    total_retenciones_ars = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Total Retenciones / Descuentos"))
    neto_a_cobrar_ars = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Sueldo Neto a Cobrar (ARS)"))
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.CALCULADO, verbose_name=_("Estado"))

    class Meta:
        verbose_name = _("Liquidación de Empleado")
        verbose_name_plural = _("Liquidaciones de Empleados")
        unique_together = ('periodo', 'empleado')
        ordering = ['empleado__apellido', 'empleado__nombre']

    def __str__(self):
        return f"{self.empleado.nombre_completo} - {self.periodo}: ${self.neto_a_cobrar_ars:,.2f}"


class ItemLiquidacion(TimeStampedModel):
    """Línea detallada del recibo de sueldo (Concepto, Base, Descuentos)."""
    class TipoConcepto(models.TextChoices):
        REMUNERATIVO = 'REMUNERATIVO', _('Haber Remunerativo')
        NO_REMUNERATIVO = 'NO_REMUNERATIVO', _('Haber No Remunerativo')
        RETENCION = 'RETENCION', _('Retención / Descuento de Ley')

    liquidacion = models.ForeignKey(
        LiquidacionEmpleado, 
        on_delete=models.CASCADE, 
        related_name='items', 
        verbose_name=_("Liquidación")
    )
    codigo_concepto = models.CharField(max_length=30, verbose_name=_("Código Concepto"))
    descripcion = models.CharField(max_length=120, verbose_name=_("Descripción Concepto"))
    tipo = models.CharField(max_length=20, choices=TipoConcepto.choices, verbose_name=_("Tipo de Concepto"))
    cantidad_o_porcentaje = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        default=1.00, 
        verbose_name=_("Unidades / %")
    )
    importe_ars = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Importe (ARS)"))

    class Meta:
        verbose_name = _("Ítem de Liquidación")
        verbose_name_plural = _("Ítems de Liquidación")

    def __str__(self):
        return f"[{self.codigo_concepto}] {self.descripcion}: ${self.importe_ars:,.2f}"
