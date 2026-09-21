import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel, Finca

class Empleado(TimeStampedModel):
    """Ficha completa del trabajador rural o personal de planta/almazara."""
    class RolLaboral(models.TextChoices):
        PEON_GENERAL = 'PEON_GENERAL', _('Peón General Rural')
        TRACTORISTA = 'TRACTORISTA', _('Tractorista / Maquinista')
        ENCARGADO_CUADRILLA = 'ENCARGADO_CUADRILLA', _('Encargado de Cuadrilla')
        CAPATAZ_FINCA = 'CAPATAZ_FINCA', _('Capataz de Finca')
        REGADOR = 'REGADOR', _('Especialista en Riego')
        PODADOR = 'PODADOR', _('Podador Especializado')
        COSECHERO = 'COSECHERO', _('Cosechero Temporario')
        MECANICO = 'MECANICO', _('Mecánico / Taller')
        OPERARIO_ALMAZARA = 'OPERARIO_ALMAZARA', _('Operario Almazara / Fábrica')
        ADMINISTRATIVO = 'ADMINISTRATIVO', _('Administración / RRHH')

    class ModalidadContratacion(models.TextChoices):
        JORNAL_RURAL = 'JORNAL', _('Jornal Diario Rural (UATRE)')
        MENSUAL = 'MENSUAL', _('Mensualizado Permanente')
        A_DESTAJO = 'DESTAJO', _('A Destajo / Al Tanto (Cosecha/Poda)')

    legajo = models.CharField(max_length=20, unique=True, verbose_name=_("Número de Legajo"))
    nombre = models.CharField(max_length=80, verbose_name=_("Nombres"))
    apellido = models.CharField(max_length=80, verbose_name=_("Apellidos"))
    dni_cuil = models.CharField(max_length=20, unique=True, verbose_name=_("CUIL / DNI"))
    rol_laboral = models.CharField(
        max_length=30, 
        choices=RolLaboral.choices, 
        default=RolLaboral.PEON_GENERAL, 
        verbose_name=_("Puesto / Categoría")
    )
    modalidad = models.CharField(
        max_length=20, 
        choices=ModalidadContratacion.choices, 
        default=ModalidadContratacion.JORNAL_RURAL, 
        verbose_name=_("Modalidad de Contratación")
    )
    finca_habitual = models.ForeignKey(
        Finca, 
        on_delete=models.PROTECT, 
        related_name='empleados_asignados', 
        verbose_name=_("Finca Habitual")
    )
    valor_jornal_base_ars = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        verbose_name=_("Valor Jornal / Sueldo Base (ARS)")
    )
    valor_hora_extra_ars = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        verbose_name=_("Valor Hora Extra (ARS)")
    )
    fecha_ingreso = models.DateField(verbose_name=_("Fecha de Ingreso"))
    telefono = models.CharField(max_length=40, blank=True, verbose_name=_("Teléfono"))
    direccion = models.CharField(max_length=200, blank=True, verbose_name=_("Dirección"))
    cbu_alias = models.CharField(max_length=60, blank=True, verbose_name=_("CBU / Alias Bancario"))
    codigo_qr_uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name=_("Código QR Único"),
        help_text=_("Identificador único para el fichaje por escaneo de QR")
    )
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))

    class Meta:
        verbose_name = _("Empleado")
        verbose_name_plural = _("Personal / Empleados")
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f"{self.apellido}, {self.nombre} ({self.legajo})"

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"


class RegistroAsistencia(TimeStampedModel):
    """Control de presentismo diario de personal de campo y fábrica."""
    class Estado(models.TextChoices):
        PRESENTE = 'PRESENTE', _('Presente')
        AUSENTE_INJUSTIFICADO = 'AUSENTE_INJUSTIFICADO', _('Ausente Injustificado')
        AUSENTE_JUSTIFICADO = 'AUSENTE_JUSTIFICADO', _('Ausente Justificado')
        LLUVIA_CLIMA = 'LLUVIA_CLIMA', _('Suspensión por Lluvia/Clima')
        ACCIDENTE_ART = 'ACCIDENTE_ART', _('Accidente / ART')
        LICENCIA = 'LICENCIA', _('Licencia / Vacaciones')
        FERIADO_TRABAJADO = 'FERIADO_TRABAJADO', _('Feriado Trabajado')

    empleado = models.ForeignKey(
        Empleado, 
        on_delete=models.CASCADE, 
        related_name='asistencias', 
        verbose_name=_("Empleado")
    )
    finca = models.ForeignKey(
        Finca, 
        on_delete=models.CASCADE, 
        related_name='asistencias_diarias', 
        verbose_name=_("Finca de Jornada")
    )
    fecha = models.DateField(verbose_name=_("Fecha"))
    estado = models.CharField(
        max_length=30, 
        choices=Estado.choices, 
        default=Estado.PRESENTE, 
        verbose_name=_("Estado de Asistencia")
    )
    horas_normales = models.DecimalField(max_digits=4, decimal_places=1, default=8.0, verbose_name=_("Horas Normales"))
    horas_extras = models.DecimalField(max_digits=4, decimal_places=1, default=0.0, verbose_name=_("Horas Extras"))
    jornal_computado = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=1.00, 
        verbose_name=_("Jornal Computado"),
        help_text=_("1.0 jornal entero, 0.5 medio jornal, 0 si ausente")
    )
    observaciones = models.CharField(max_length=200, blank=True, verbose_name=_("Observaciones"))

    class Meta:
        verbose_name = _("Registro de Asistencia")
        verbose_name_plural = _("Registros de Asistencia")
        unique_together = ('empleado', 'fecha')
        ordering = ['-fecha', 'empleado__apellido']

    def __str__(self):
        return f"{self.fecha} - {self.empleado}: {self.get_estado_display()} ({self.jornal_computado} jornales)"


class Inscripcion(TimeStampedModel):
    """Proceso de solicitud, alta temprana y validación de nuevo personal rural."""
    class EstadoInscripcion(models.TextChoices):
        POSTULADO = 'POSTULADO', _('Postulación Recibida')
        EN_EVALUACION = 'EN_EVALUACION', _('En Evaluación Médica/Antecedentes')
        ALTA_AFIP = 'ALTA_AFIP', _('Alta Temprana AFIP Generada')
        CONTRATADO = 'CONTRATADO', _('Contratado / Activo en ERP')
        RECHAZADO = 'RECHAZADO', _('Rechazado / Descartado')

    dni_cuil = models.CharField(max_length=20, unique=True, verbose_name=_("DNI / CUIL"))
    nombre = models.CharField(max_length=80, verbose_name=_("Nombres"))
    apellido = models.CharField(max_length=80, verbose_name=_("Apellidos"))
    telefono = models.CharField(max_length=40, verbose_name=_("Teléfono de Contacto"))
    puesto_aspirado = models.CharField(max_length=80, verbose_name=_("Puesto Aspirado"))
    finca_postulada = models.ForeignKey(Finca, on_delete=models.CASCADE, verbose_name=_("Finca de Trabajo"))
    alta_temprana_afip_numero = models.CharField(max_length=50, blank=True, verbose_name=_("N° Alta Temprana AFIP"))
    apto_medico = models.BooleanField(default=False, verbose_name=_("Apto Médico Vigente"))
    estado = models.CharField(
        max_length=25, 
        choices=EstadoInscripcion.choices, 
        default=EstadoInscripcion.POSTULADO, 
        verbose_name=_("Estado de la Solicitud")
    )
    observaciones = models.TextField(blank=True, verbose_name=_("Observaciones"))
    empleado_generado = models.OneToOneField(
        Empleado, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='inscripcion_origen', 
        verbose_name=_("Legajo Creado")
    )

    class Meta:
        verbose_name = _("Inscripción de Personal")
        verbose_name_plural = _("Inscripciones y Altas de Personal")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.apellido}, {self.nombre} ({self.get_estado_display()})"
