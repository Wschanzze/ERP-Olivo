from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

class TimeStampedModel(models.Model):
    """Modelo base abstracto con marcas de tiempo."""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha de Creación"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Última Modificación"))

    class Meta:
        abstract = True


class Empresa(TimeStampedModel):
    """Datos de la empresa agroindustrial productora olivícola."""
    razon_social = models.CharField(max_length=200, verbose_name=_("Razón Social"))
    nombre_fantasia = models.CharField(max_length=150, blank=True, verbose_name=_("Nombre de Fantasía"))
    cuit = models.CharField(max_length=20, unique=True, verbose_name=_("CUIT"))
    direccion = models.CharField(max_length=255, blank=True, verbose_name=_("Dirección Legal"))
    telefono = models.CharField(max_length=50, blank=True, verbose_name=_("Teléfono"))
    email = models.EmailField(blank=True, verbose_name=_("Correo Electrónico"))
    moneda_principal = models.CharField(max_length=5, default='ARS', verbose_name=_("Moneda Principal"))
    moneda_secundaria = models.CharField(max_length=5, default='USD', verbose_name=_("Moneda Secundaria"))
    logo = models.ImageField(upload_to='empresa/logos/', blank=True, null=True, verbose_name=_("Logo"))

    class Meta:
        verbose_name = _("Empresa")
        verbose_name_plural = _("Empresas")

    def __str__(self):
        return self.nombre_fantasia or self.razon_social


class Finca(TimeStampedModel):
    """Representa cada una de las fincas/establecimientos agrícolas de la empresa."""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='fincas', verbose_name=_("Empresa"))
    nombre = models.CharField(max_length=120, verbose_name=_("Nombre de la Finca"))
    codigo = models.CharField(max_length=30, unique=True, verbose_name=_("Código Finca"))
    superficie_total_ha = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_("Superficie Total (ha)"))
    ubicacion = models.CharField(max_length=255, blank=True, verbose_name=_("Ubicación / Localidad"))
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name=_("Latitud"))
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name=_("Longitud"))
    
    TIPO_RIEGO_CHOICES = [
        ('GOTEO', 'Riego por Goteo'),
        ('ASPERSION', 'Microaspersión'),
        ('SURCO', 'Manto / Surco'),
        ('MIXTO', 'Mixto'),
        ('SECANO', 'Secano'),
    ]
    tipo_riego_principal = models.CharField(
        max_length=20, 
        choices=TIPO_RIEGO_CHOICES, 
        default='GOTEO', 
        verbose_name=_("Tipo de Riego Principal")
    )
    activa = models.BooleanField(default=True, verbose_name=_("Activa"))

    class Meta:
        verbose_name = _("Finca")
        verbose_name_plural = _("Fincas")
        ordering = ['nombre']
        permissions = (
            ('administrar_finca', 'Puede administrar finca'),
            ('ver_finca', 'Puede ver datos de la finca'),
        )

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"


class CentroDeCosto(TimeStampedModel):
    """Estructura de imputación de costos para control de gestión agrícola y fabril."""
    TIPO_CHOICES = [
        ('PRODUCTIVO_CAMPO', 'Productivo Agrícola (Fincas/Cuadros)'),
        ('FABRICA_ALMAZARA', 'Fábrica / Almazara (Elaboración Aceite/Aceituna)'),
        ('MAQUINARIA_TALLER', 'Taller y Maquinaria'),
        ('ESTRUCTURA_ADMIN', 'Estructura y Administración'),
        ('COMERCIAL_EXPORT', 'Comercial y Exportación'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='centros_de_costo', verbose_name=_("Empresa"))
    codigo = models.CharField(max_length=40, unique=True, verbose_name=_("Código Contable"))
    nombre = models.CharField(max_length=150, verbose_name=_("Nombre del Centro de Costo"))
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default='PRODUCTIVO_CAMPO', verbose_name=_("Tipo"))
    finca = models.ForeignKey(Finca, on_delete=models.SET_NULL, null=True, blank=True, related_name='centros_de_costo', verbose_name=_("Finca Asociada"))
    cuenta_contable_defecto = models.ForeignKey(
        'finanzas.CuentaContable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='centros_de_costo',
        verbose_name=_("Cuenta Contable por Defecto"),
        help_text=_("Cuenta de costo o gasto asociada habitualmente a este centro.")
    )
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))

    class Meta:
        verbose_name = _("Centro de Costo")
        verbose_name_plural = _("Centros de Costo")
        ordering = ['codigo']

    def __str__(self):
        return f"[{self.codigo}] {self.nombre}"


class Usuario(AbstractUser):
    """Modelo de Usuario extendido con roles específicos del negocio olivícola."""
    class Rol(models.TextChoices):
        ADMIN_GENERAL = 'ADMIN_GENERAL', _('Administrador General')
        RESPONSABLE_FINCA = 'RESPONSABLE_FINCA', _('Responsable de Finca')
        ENCARGADO_CAMPO = 'ENCARGADO_CAMPO', _('Encargado de Campo')
        INGENIERO_AGRONOMO = 'INGENIERO_AGRONOMO', _('Ingeniero Agrónomo')
        CONTABLE = 'CONTABLE', _('Responsable Contable / Finanzas')
        RRHH = 'RRHH', _('Recursos Humanos')
        OPERARIO = 'OPERARIO', _('Operario / Capataz')

    rol = models.CharField(
        max_length=25, 
        choices=Rol.choices, 
        default=Rol.ADMIN_GENERAL, 
        verbose_name=_("Rol en el Sistema")
    )
    telefono = models.CharField(max_length=40, blank=True, verbose_name=_("Teléfono"))
    finca_predeterminada = models.ForeignKey(
        Finca, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='usuarios_asignados', 
        verbose_name=_("Finca Predeterminada")
    )
    supabase_uid = models.CharField(
        max_length=64, 
        blank=True, 
        null=True, 
        unique=True, 
        verbose_name=_("UID Supabase")
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name=_("Avatar"))

    class Meta:
        verbose_name = _("Usuario")
        verbose_name_plural = _("Usuarios")

    @property
    def iniciales(self):
        """Iniciales para el avatar en el header."""
        first = self.first_name[0].upper() if self.first_name else ''
        last = self.last_name[0].upper() if self.last_name else ''
        if not first and not last:
            return self.username[:2].upper()
        return f"{first}{last}"

    @property
    def is_admin_general(self):
        return self.rol == self.Rol.ADMIN_GENERAL or self.is_superuser

    @property
    def is_contable(self):
        return self.rol in (self.Rol.CONTABLE, self.Rol.ADMIN_GENERAL) or self.is_superuser

    @property
    def is_encargado_campo(self):
        return self.rol in (self.Rol.ENCARGADO_CAMPO, self.Rol.RESPONSABLE_FINCA, self.Rol.ADMIN_GENERAL) or self.is_superuser

    @property
    def is_rrhh(self):
        return self.rol in (self.Rol.RRHH, self.Rol.ADMIN_GENERAL) or self.is_superuser

    def puede_acceder_modulo(self, modulo: str) -> bool:
        """Determina si el usuario tiene permiso para acceder a un módulo específico del ERP."""
        if not self.is_active:
            return False
        if self.is_superuser or self.rol == self.Rol.ADMIN_GENERAL:
            return True

        modulo_key = (modulo or '').lower().strip()
        PERMISOS_MODULOS = {
            'tableros': [
                self.Rol.RESPONSABLE_FINCA, self.Rol.ENCARGADO_CAMPO,
                self.Rol.INGENIERO_AGRONOMO, self.Rol.CONTABLE,
                self.Rol.RRHH, self.Rol.OPERARIO
            ],
            'campo': [
                self.Rol.RESPONSABLE_FINCA, self.Rol.ENCARGADO_CAMPO,
                self.Rol.INGENIERO_AGRONOMO, self.Rol.OPERARIO
            ],
            'campos': [
                self.Rol.RESPONSABLE_FINCA, self.Rol.ENCARGADO_CAMPO,
                self.Rol.INGENIERO_AGRONOMO, self.Rol.OPERARIO
            ],
            'parte-diario': [
                self.Rol.RESPONSABLE_FINCA, self.Rol.ENCARGADO_CAMPO,
                self.Rol.INGENIERO_AGRONOMO, self.Rol.OPERARIO
            ],
            'finanzas': [self.Rol.CONTABLE],
            'costos': [self.Rol.CONTABLE, self.Rol.RESPONSABLE_FINCA],
            'personal': [self.Rol.RRHH, self.Rol.CONTABLE],
            'liquidacion': [self.Rol.RRHH, self.Rol.CONTABLE],
            'inventario': [
                self.Rol.RESPONSABLE_FINCA, self.Rol.ENCARGADO_CAMPO,
                self.Rol.CONTABLE, self.Rol.OPERARIO
            ],
            'almazara': [
                self.Rol.RESPONSABLE_FINCA, self.Rol.ENCARGADO_CAMPO,
                self.Rol.CONTABLE, self.Rol.OPERARIO
            ],
            'usuarios': [],  # Sólo Administrador General
        }
        permitidos = PERMISOS_MODULOS.get(modulo_key, [])
        return self.rol in permitidos

    @property
    def puede_ver_tableros(self):
        return self.puede_acceder_modulo('tableros')

    @property
    def puede_ver_campo(self):
        return self.puede_acceder_modulo('campo')

    @property
    def puede_ver_finanzas(self):
        return self.puede_acceder_modulo('finanzas')

    @property
    def puede_ver_costos(self):
        return self.puede_acceder_modulo('costos')

    @property
    def puede_ver_personal(self):
        return self.puede_acceder_modulo('personal')

    @property
    def puede_ver_almazara(self):
        return self.puede_acceder_modulo('inventario')


