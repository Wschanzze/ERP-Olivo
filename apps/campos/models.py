from django.db import models
from django.conf import settings
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

    @property
    def registro_fenologico_actual(self):
        return self.registros_fenologicos.order_by('-fecha').first()

    @property
    def semaforo_fitosanitario(self):
        reg = self.registro_fenologico_actual
        if not reg:
            return 'gris'
        return reg.semaforo


class RegistroFenologico(TimeStampedModel):
    """Registro del estado fenológico y sanitario de un cuadro en una campaña."""
    class FaseVegetativa(models.TextChoices):
        REPOSO = 'REPOSO', _('Reposo Invernal')
        BROTACION = 'BROTACION', _('Brotación / Hinchazón Yemas')
        FLORACION = 'FLORACION', _('Floración')
        CUAJADO = 'CUAJADO', _('Cuajado de Frutos')
        CRECIMIENTO = 'CRECIMIENTO', _('Crecimiento del Fruto')
        ENVERO = 'ENVERO', _('Envero / Cambio de Color')
        MADUREZ = 'MADUREZ', _('Madurez Comercial')
        POSTCOSECHA = 'POSTCOSECHA', _('Post-Cosecha')

    class RiesgoFitosanitario(models.TextChoices):
        BAJO = 'BAJO', _('Sin riesgo aparente')
        MODERADO = 'MODERADO', _('Monitoreo requerido')
        ALTO = 'ALTO', _('Intervención urgente')

    cuadro = models.ForeignKey(Cuadro, on_delete=models.CASCADE, related_name='registros_fenologicos', verbose_name=_("Cuadro"))
    campana = models.CharField(max_length=20, verbose_name=_("Campaña Agrícola"), help_text=_("Ej: 2025/2026"))
    fecha = models.DateField(verbose_name=_("Fecha de Observación"))
    fase_vegetativa = models.CharField(max_length=20, choices=FaseVegetativa.choices, default=FaseVegetativa.BROTACION, verbose_name=_("Fase Fenológica"))
    grados_dia_acumulados = models.DecimalField(max_digits=7, decimal_places=1, default=0.0, verbose_name=_("GDC Acumulados"), help_text=_("Grados Día de Crecimiento desde inicio de campaña"))
    temperatura_min = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name=_("Temp. Mínima (°C)"))
    temperatura_max = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name=_("Temp. Máxima (°C)"))
    riesgo_fitosanitario = models.CharField(max_length=10, choices=RiesgoFitosanitario.choices, default=RiesgoFitosanitario.BAJO, verbose_name=_("Riesgo Fitosanitario"))
    observaciones = models.TextField(blank=True, verbose_name=_("Observaciones Agronómicas"))
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Técnico / Agrónomo"))

    class Meta:
        verbose_name = _("Registro Fenológico")
        verbose_name_plural = _("Registros Fenológicos")
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.cuadro.codigo} — {self.get_fase_vegetativa_display()} ({self.fecha})"

    @property
    def semaforo(self):
        mapa = {'BAJO': 'verde', 'MODERADO': 'amarillo', 'ALTO': 'rojo'}
        return mapa.get(self.riesgo_fitosanitario, 'gris')


class EventoCuadro(TimeStampedModel):
    """Historial de intervenciones y eventos agronómicos registrados en un cuadro."""
    class TipoEvento(models.TextChoices):
        PODA = 'PODA', _('Poda')
        RALEO_FRUTOS = 'RALEO', _('Raleo de Frutos')
        RIEGO_AUXILIO = 'RIEGO_AUXILIO', _('Riego de Auxilio')
        APLICACION_FITOSANITARIA = 'FITOSANITARIO', _('Aplicación Fitosanitaria')
        FERTILIZACION = 'FERTILIZACION', _('Fertilización')
        ANALISIS_SUELO = 'ANALISIS_SUELO', _('Análisis de Suelo')
        ANALISIS_FOLIAR = 'ANALISIS_FOLIAR', _('Análisis Foliar')
        VISITA_TECNICA = 'VISITA_TECNICA', _('Visita Técnica / Agronómica')
        OTRO = 'OTRO', _('Otro Evento')

    cuadro = models.ForeignKey(Cuadro, on_delete=models.CASCADE, related_name='eventos', verbose_name=_("Cuadro"))
    campana = models.CharField(max_length=20, verbose_name=_("Campaña"))
    tipo_evento = models.CharField(max_length=25, choices=TipoEvento.choices, verbose_name=_("Tipo de Evento"))
    fecha = models.DateField(verbose_name=_("Fecha"))
    descripcion = models.TextField(verbose_name=_("Descripción / Detalle"))
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Responsable"))

    class Meta:
        verbose_name = _("Evento de Cuadro")
        verbose_name_plural = _("Eventos de Cuadros")
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.get_tipo_evento_display()} en {self.cuadro.codigo} ({self.fecha})"


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
        indexes = [
            models.Index(fields=['campana']),
            models.Index(fields=['cuadro', 'campana']),
        ]

    def __str__(self):
        return f"Cosecha {self.campana} - {self.cuadro} ({self.kg_cosechados:,.0f} kg)"

    @property
    def rinde_por_hectarea_kg(self):
        if self.cuadro.hectareas_netas > 0:
            return round(self.kg_cosechados / self.cuadro.hectareas_netas, 2)
        return 0
