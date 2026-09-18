from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel, CentroDeCosto, Finca
from apps.campos.models import Cuadro

class CostoPorCentro(TimeStampedModel):
    """Asignación de costos directos e indirectos por centro de costo y lote agrícola."""
    class TipoOrigen(models.TextChoices):
        MANO_DE_OBRA = 'MANO_DE_OBRA', _('Mano de Obra (Jornales/Horas)')
        INSUMO = 'INSUMO', _('Insumos Agrícolas (Agroquímicos/Fertilizantes)')
        COMBUSTIBLE_MAQUINARIA = 'COMBUSTIBLE', _('Combustible y Maquinaria')
        SERVICIO_CONTRATISTA = 'CONTRATISTA', _('Servicios de Contratistas / Terceros')
        ENERGIA_RIEGO = 'ENERGIA_RIEGO', _('Energía Eléctrica y Riego')
        MANTENIMIENTO = 'MANTENIMIENTO', _('Mantenimiento y Reparaciones')
        ESTRUCTURA_ADMIN = 'ESTRUCTURA_ADMIN', _('Costos de Estructura / Administración')

    centro_de_costo = models.ForeignKey(
        CentroDeCosto, 
        on_delete=models.PROTECT, 
        related_name='costos_registrados', 
        verbose_name=_("Centro de Costo")
    )
    finca = models.ForeignKey(
        Finca, 
        on_delete=models.PROTECT, 
        related_name='costos_finca', 
        verbose_name=_("Finca")
    )
    cuadro = models.ForeignKey(
        Cuadro, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='costos_directos', 
        verbose_name=_("Cuadro / Cuartel (opcional si es directo)")
    )
    fecha = models.DateField(verbose_name=_("Fecha de Imputación"))
    importe_ars = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Importe (ARS)"))
    importe_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Importe (USD)"))
    tipo_origen = models.CharField(
        max_length=30, 
        choices=TipoOrigen.choices, 
        verbose_name=_("Tipo de Origen / Concepto")
    )
    descripcion = models.CharField(max_length=255, verbose_name=_("Descripción / Detalle"))
    documento_origen_tipo = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name=_("Tipo de Documento Origen"),
        help_text=_("Ej: ParteDiario, MovimientoStock, FacturaProveedor")
    )
    documento_origen_id = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        verbose_name=_("ID de Documento Origen")
    )

    class Meta:
        verbose_name = _("Costo por Centro")
        verbose_name_plural = _("Costos por Centro")
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['centro_de_costo', 'fecha']),
            models.Index(fields=['finca', 'fecha']),
            models.Index(fields=['cuadro', 'fecha']),
            models.Index(fields=['documento_origen_tipo', 'documento_origen_id']),
        ]

    def __str__(self):
        return f"{self.fecha} - {self.centro_de_costo.codigo}: ${self.importe_ars:,.2f} ({self.get_tipo_origen_display()})"
