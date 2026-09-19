from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel, Empresa, Finca, CentroDeCosto

class Cuenta(TimeStampedModel):
    """Cajas físicas y cuentas bancarias en moneda local y extranjera."""
    class TipoCuenta(models.TextChoices):
        CAJA_EFECTIVO = 'CAJA_EFECTIVO', _('Caja Chica / Efectivo en Finca')
        CUENTA_BANCARIA = 'BANCO', _('Cuenta Corriente / Caja de Ahorro Bancaria')
        BILLETERA_VIRTUAL = 'VIRTUAL', _('Billetera Virtual / Mercado Pago')

    class Moneda(models.TextChoices):
        ARS = 'ARS', _('Pesos Argentinos (ARS)')
        USD = 'USD', _('Dólares Estadounidenses (USD)')

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='cuentas_financieras', verbose_name=_("Empresa"))
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre de la Cuenta"))
    tipo = models.CharField(max_length=20, choices=TipoCuenta.choices, default=TipoCuenta.CUENTA_BANCARIA, verbose_name=_("Tipo"))
    moneda = models.CharField(max_length=5, choices=Moneda.choices, default=Moneda.ARS, verbose_name=_("Moneda"))
    banco_nombre = models.CharField(max_length=80, blank=True, verbose_name=_("Banco"))
    numero_cuenta = models.CharField(max_length=50, blank=True, verbose_name=_("N° de Cuenta"))
    cbu_cvu = models.CharField(max_length=30, blank=True, verbose_name=_("CBU / CVU / Alias"))
    saldo_actual = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Saldo Actual"))
    activa = models.BooleanField(default=True, verbose_name=_("Activa"))

    class Meta:
        verbose_name = _("Cuenta Financiera / Caja")
        verbose_name_plural = _("Cuentas Financieras y Cajas")
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.moneda} ${self.saldo_actual:,.2f})"


class CuentaCorriente(TimeStampedModel):
    """Libreta de cuentas corrientes para Proveedores de insumos y Clientes de exportación."""
    class TipoEntidad(models.TextChoices):
        PROVEEDOR = 'PROVEEDOR', _('Proveedor (Insumos, Servicios, Contratistas)')
        CLIENTE = 'CLIENTE', _('Cliente (Aceitera, Mayorista, Exportación)')

    tipo_entidad = models.CharField(max_length=20, choices=TipoEntidad.choices, verbose_name=_("Tipo de Entidad"))
    razon_social = models.CharField(max_length=180, verbose_name=_("Razón Social"))
    nombre_comercial = models.CharField(max_length=150, blank=True, verbose_name=_("Nombre Comercial"))
    cuit = models.CharField(max_length=20, unique=True, verbose_name=_("CUIT / Identificación Fiscal"))
    email = models.EmailField(blank=True, verbose_name=_("Correo Electrónico"))
    telefono = models.CharField(max_length=50, blank=True, verbose_name=_("Teléfono"))
    direccion = models.CharField(max_length=200, blank=True, verbose_name=_("Dirección Comercial"))
    saldo_actual = models.DecimalField(
        max_digits=14, 
        decimal_places=2, 
        default=0.00, 
        verbose_name=_("Saldo Actual"),
        help_text=_("Para Proveedor: saldo negativo = debemos pagarle. Para Cliente: saldo positivo = nos debe cobrar.")
    )
    limite_credito = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Límite de Crédito"))
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))

    class Meta:
        verbose_name = _("Cuenta Corriente")
        verbose_name_plural = _("Cuentas Corrientes (Proveedores y Clientes)")
        ordering = ['razon_social']

    def __str__(self):
        return f"[{self.get_tipo_entidad_display()}] {self.razon_social} (Saldo: ${self.saldo_actual:,.2f})"


class MovimientoFinanciero(TimeStampedModel):
    """Ingresos, egresos y transferencias que afectan caja, bancos y cuentas corrientes."""
    class TipoMovimiento(models.TextChoices):
        INGRESO = 'INGRESO', _('Ingreso / Cobro')
        EGRESO = 'EGRESO', _('Egreso / Pago')
        TRANSFERENCIA = 'TRANSFERENCIA', _('Transferencia entre Cuentas')

    cuenta = models.ForeignKey(
        Cuenta, 
        on_delete=models.PROTECT, 
        related_name='movimientos', 
        verbose_name=_("Cuenta Origen / Principal")
    )
    cuenta_destino = models.ForeignKey(
        Cuenta, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='transferencias_entrantes', 
        verbose_name=_("Cuenta Destino (si es transf.)")
    )
    tipo = models.CharField(max_length=20, choices=TipoMovimiento.choices, verbose_name=_("Tipo de Movimiento"))
    fecha = models.DateField(verbose_name=_("Fecha"))
    importe = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Importe"))
    moneda = models.CharField(max_length=5, default='ARS', verbose_name=_("Moneda"))
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000, verbose_name=_("Tipo de Cambio"))
    concepto = models.CharField(max_length=200, verbose_name=_("Concepto / Detalle"))
    comprobante_tipo = models.CharField(max_length=50, blank=True, verbose_name=_("Tipo Comprobante (Factura, Recibo)"))
    comprobante_nro = models.CharField(max_length=50, blank=True, verbose_name=_("N° Comprobante"))
    conciliado = models.BooleanField(default=False, verbose_name=_("Conciliado"))
    cuenta_corriente = models.ForeignKey(
        CuentaCorriente, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='movimientos_financieros', 
        verbose_name=_("Cuenta Corriente (Proveedor/Cliente)")
    )
    centro_de_costo = models.ForeignKey(
        CentroDeCosto, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='movimientos_financieros', 
        verbose_name=_("Centro de Costo Imputable")
    )
    finca = models.ForeignKey(
        Finca, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='movimientos_financieros', 
        verbose_name=_("Finca Imputable")
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name=_("Usuario Registrador")
    )

    class Meta:
        verbose_name = _("Movimiento Financiero")
        verbose_name_plural = _("Movimientos Financieros")
        ordering = ['-fecha', '-created_at']

    def __str__(self):
        return f"{self.fecha} - {self.get_tipo_display()} ${self.importe:,.2f} ({self.concepto})"


class Cheque(TimeStampedModel):
    """Gestión de cheques de pago diferido (propios emitidos y de clientes en cartera)."""
    class TipoCheque(models.TextChoices):
        RECIBIDO_TERCERO = 'RECIBIDO', _('Recibido de Cliente (En Cartera)')
        EMITIDO_PROPIO = 'EMITIDO', _('Emitido Propio (Cheque Diferido)')

    class EstadoCheque(models.TextChoices):
        EN_CARTERA = 'EN_CARTERA', _('En Cartera')
        DEPOSITADO = 'DEPOSITADO', _('Depositado en Banco')
        COBRADO = 'COBRADO', _('Cobrado / Acreditado')
        ENTREGADO_PROVEEDOR = 'ENTREGADO_PROVEEDOR', _('Entregado / Endosado a Proveedor')
        RECHAZADO = 'RECHAZADO', _('Rechazado')
        ANULADO = 'ANULADO', _('Anulado')

    tipo = models.CharField(max_length=15, choices=TipoCheque.choices, verbose_name=_("Tipo de Cheque"))
    banco_emisor = models.CharField(max_length=80, verbose_name=_("Banco Emisor"))
    numero = models.CharField(max_length=40, verbose_name=_("Número de Cheque"))
    emisor_firmante = models.CharField(max_length=120, verbose_name=_("Emisor / Firmante"))
    cuit_emisor = models.CharField(max_length=20, blank=True, verbose_name=_("CUIT Emisor"))
    fecha_emision = models.DateField(verbose_name=_("Fecha de Emisión"))
    fecha_cobro = models.DateField(verbose_name=_("Fecha de Cobro / Vencimiento"))
    importe = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Importe (ARS)"))
    cuenta_bancaria_origen = models.ForeignKey(
        Cuenta, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='cheques_emitidos', 
        verbose_name=_("Cuenta Bancaria (si es propio)")
    )
    cuenta_corriente = models.ForeignKey(
        CuentaCorriente, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='cheques_asociados', 
        verbose_name=_("Cliente / Proveedor Vinculado")
    )
    estado = models.CharField(
        max_length=25, 
        choices=EstadoCheque.choices, 
        default=EstadoCheque.EN_CARTERA, 
        verbose_name=_("Estado")
    )
    observaciones = models.TextField(blank=True, verbose_name=_("Observaciones"))

    class Meta:
        verbose_name = _("Cheque")
        verbose_name_plural = _("Cheques (Cartera y Emitidos)")
        ordering = ['fecha_cobro']

    def __str__(self):
        return f"Cheque {self.banco_emisor} #{self.numero} - ${self.importe:,.2f} ({self.get_estado_display()})"


class ConciliacionBancaria(TimeStampedModel):
    """Proceso de conciliación entre los movimientos del sistema y el extracto bancario."""
    class EstadoConciliacion(models.TextChoices):
        BORRADOR = 'BORRADOR', _('En Proceso')
        CERRADA = 'CERRADA', _('Conciliación Cerrada')

    cuenta = models.ForeignKey(
        Cuenta,
        on_delete=models.PROTECT,
        related_name='conciliaciones',
        verbose_name=_("Cuenta Bancaria")
    )
    fecha_extracto = models.DateField(verbose_name=_("Fecha de Corte del Extracto"))
    saldo_extracto = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Saldo según Extracto"))
    saldo_sistema = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Saldo según Sistema"))
    diferencia = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name=_("Diferencia"))
    estado = models.CharField(
        max_length=15,
        choices=EstadoConciliacion.choices,
        default=EstadoConciliacion.BORRADOR,
        verbose_name=_("Estado")
    )
    movimientos_conciliados = models.ManyToManyField(
        MovimientoFinanciero,
        blank=True,
        related_name='conciliaciones_asociadas',
        verbose_name=_("Movimientos Conciliados")
    )
    observaciones = models.TextField(blank=True, verbose_name=_("Observaciones"))
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Usuario")
    )

    class Meta:
        verbose_name = _("Conciliación Bancaria")
        verbose_name_plural = _("Conciliaciones Bancarias")
        ordering = ['-fecha_extracto']

    def __str__(self):
        return f"Conciliación {self.cuenta.nombre} — {self.fecha_extracto} ({self.get_estado_display()})"
