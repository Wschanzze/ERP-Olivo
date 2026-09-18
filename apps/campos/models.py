from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel, Finca

class Cuadro(TimeStampedModel):
    """Representa un cuadro o cuartel dentro de una finca con características agronómicas específicas."""
    class VariedadOlivo(models.TextChoices):
        ARAUCO = 'ARAUCO', _('Arauco (Criolla)')
        ARBEQUINA = 'ARBEQUINA', _('Arbequina')
        PICUAL = 'PICUAL', _('Picual')
        FRANTOIO = 'FRANTOIO', _('Frantoio')
        MANZANILLA = 'MANZANILLA', _('Manzanilla')
        CORATINA = 'CORATINA', _('Coratina')
        CHANGLOT = 'CHANGLOT', _('Changlot Real')
        HOJIBLANCA = 'HOJIBLANCA', _('Hojiblanca')
        EMPELTRE = 'EMPELTRE', _('Empeltre')
        OTRA = 'OTRA', _('Otra Variedad')

    finca = models.ForeignKey(Finca, on_delete=models.CASCADE, related_name='cuadros', verbose_name=_("Finca"))
    codigo = models.CharField(max_length=30, verbose_name=_("Código de Cuadro"))
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre / Denominación"))
    hectareas_netas = models.DecimalField(max_digits=7, decimal_places=2, verbose_name=_("Hectáreas Netas"))
    variedad_olivo = models.CharField(
        max_length=30, 
        choices=VariedadOlivo.choices, 
        default=VariedadOlivo.ARAUCO, 
        verbose_name=_("Variedad de Olivo")
    )
    ano_plantacion = models.PositiveIntegerField(verbose_name=_("Año de Plantación"))
    densidad_plantas_ha = models.PositiveIntegerField(
        default=300, 
        verbose_name=_("Densidad (plantas/ha)"),
        help_text=_("Ej: 250-400 tradicional, 800 intensivo, 1600+ superintensivo")
    )
    marco_plantacion = models.CharField(
        max_length=30, 
        blank=True, 
        verbose_name=_("Marco de Plantación"),
        help_text=_("Ej: 7x5 m, 6x4 m, 4x1.5 m")
    )
    SISTEMA_RIEGO_CHOICES = [
        ('GOTEO', 'Goteo automatizado'),
        ('SURCO', 'Surco / Inundación'),
        ('ASPERSION', 'Microaspersión'),
        ('SECANO', 'Secano'),
    ]
    sistema_riego = models.CharField(
        max_length=20, 
        choices=SISTEMA_RIEGO_CHOICES, 
        default='GOTEO', 
        verbose_name=_("Sistema de Riego")
    )
    estado_fitosanitario = models.CharField(
        max_length=100, 
        blank=True, 
        default='Óptimo', 
        verbose_name=_("Estado Fitosanitario")
    )
    observaciones = models.TextField(blank=True, verbose_name=_("Observaciones Agronómicas"))
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))

    class Meta:
        verbose_name = _("Cuadro")
        verbose_name_plural = _("Cuadros")
        unique_together = ('finca', 'codigo')
        ordering = ['finca', 'codigo']
        permissions = (
            ('gestionar_cuadro', 'Puede gestionar y editar cuadro'),
        )

    def __str__(self):
        return f"{self.finca.codigo} - {self.codigo} ({self.get_variedad_olivo_display()})"

    @property
    def total_estimado_plantas(self):
        return int(self.hectareas_netas * self.densidad_plantas_ha)


class LoteDeCosecha(TimeStampedModel):
    """Registro de la recolección/cosecha de un cuadro en una campaña específica."""
    class Destino(models.TextChoices):
        ACEITE_ALMAZARA = 'ACEITE_ALMAZARA', _('Aceite de Oliva (Almazara)')
        ACEITUNA_MESA_VERDE = 'ACEITUNA_MESA_VERDE', _('Aceituna de Mesa (Verde)')
        ACEITUNA_MESA_NEGRA = 'ACEITUNA_MESA_NEGRA', _('Aceituna de Mesa (Negra / Madura)')

    class Estado(models.TextChoices):
        EN_CURSO = 'EN_CURSO', _('En Curso')
        FINALIZADO = 'FINALIZADO', _('Finalizado')
        LIQUIDADO = 'LIQUIDADO', _('Liquidado a Fábrica')

    cuadro = models.ForeignKey(Cuadro, on_delete=models.CASCADE, related_name='lotes_cosecha', verbose_name=_("Cuadro"))
    campana = models.CharField(max_length=20, verbose_name=_("Campaña Agrícola"), help_text=_("Ej: 2025/2026"))
    fecha_inicio = models.DateField(verbose_name=_("Fecha de Inicio"))
    fecha_fin = models.DateField(null=True, blank=True, verbose_name=_("Fecha de Finalización"))
    kg_cosechados = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name=_("Kilogramos Cosechados"))
    destino = models.CharField(
        max_length=30, 
        choices=Destino.choices, 
        default=Destino.ACEITE_ALMAZARA, 
        verbose_name=_("Destino de la Cosecha")
    )
    rendimiento_graso_porcentaje = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name=_("Rendimiento Graso (%)"),
        help_text=_("Porcentaje de materia grasa estimado en laboratorio para almazara")
    )
    calidad_observaciones = models.TextField(blank=True, verbose_name=_("Notas de Calidad / Acidez"))
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.EN_CURSO, verbose_name=_("Estado"))

    class Meta:
        verbose_name = _("Lote de Cosecha")
        verbose_name_plural = _("Lotes de Cosecha")
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f"Cosecha {self.campana} - {self.cuadro} ({self.kg_cosechados:,.0f} kg)"

    @property
    def rinde_por_hectarea_kg(self):
        if self.cuadro.hectareas_netas > 0:
            return round(self.kg_cosechados / self.cuadro.hectareas_netas, 2)
        return 0
