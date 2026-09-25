from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel, Empresa, Finca, CentroDeCosto

class CuentaContable(TimeStampedModel):
    """Plan de cuentas contable estructurado de la empresa agropecuaria e industrial olivícola."""
    class SaldoHabitual(models.TextChoices):
        DEUDOR = 'DEUDOR', _('Deudor')
        ACREEDOR = 'ACREEDOR', _('Acreedor')

    class ClaseCuenta(models.TextChoices):
        ACTIVO = 'ACTIVO', _('Activo')
        ACTIVO_REGULARIZADORA = 'ACTIVO_REG', _('Activo (regularizadora)')
        PASIVO = 'PASIVO', _('Pasivo')
        PATRIMONIO_NETO = 'PATRIMONIO_NETO', _('Patrimonio Neto')
        RESULTADO_POSITIVO = 'RESULTADO_POSITIVO', _('Resultado Positivo (Ingreso)')
        RESULTADO_NEGATIVO = 'RESULTADO_NEGATIVO', _('Resultado Negativo (Egreso/Costo)')
        OTRO = 'OTRO', _('Otro')

    codigo = models.CharField(max_length=30, unique=True, db_index=True, verbose_name=_("Código de Cuenta"))
    nombre = models.CharField(max_length=200, verbose_name=_("Rubro / Nombre de la Cuenta"))
    nivel = models.PositiveSmallIntegerField(default=1, verbose_name=_("Nivel Jerárquico"))
    padre = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcuentas',
        verbose_name=_("Cuenta Padre / Rubro Superior")
    )
    saldo_habitual = models.CharField(
        max_length=15,
        choices=SaldoHabitual.choices,
        blank=True,
        default='',
        verbose_name=_("Saldo Habitual")
    )
    clase = models.CharField(
        max_length=30,
        choices=ClaseCuenta.choices,
        blank=True,
        default='',
        verbose_name=_("Clase Contable")
    )
    es_imputable = models.BooleanField(
        default=False,
        verbose_name=_("¿Es Imputable?"),
        help_text=_("Indica si permite imputación de asientos y vinculación con documentos directos.")
    )
    nota = models.TextField(
        blank=True,
        verbose_name=_("Nota Técnica / Criterio Olivícola"),
        help_text=_("Criterio agronómico o industrial (NIC 41, almazara, exportación, etc.)")
    )
    activa = models.BooleanField(default=True, verbose_name=_("Activa"))

    class Meta:
        verbose_name = _("Cuenta Contable")
        verbose_name_plural = _("Plan de Cuentas")
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    @property
    def tiene_hijos(self):
        return self.subcuentas.exists()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete('plan_cuentas_payload')


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
    cuenta_contable = models.ForeignKey(
        CuentaContable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cuentas_financieras',
        verbose_name=_("Cuenta Contable Asociada"),
        help_text=_("Cuenta del Plan de Cuentas correspondiente a esta caja o banco.")
    )
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
    tipo = models.CharField(max_length=20, choices=TipoMovimiento.choices, db_index=True, verbose_name=_("Tipo de Movimiento"))
    fecha = models.DateField(db_index=True, verbose_name=_("Fecha"))
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
        indexes = [
            models.Index(fields=['fecha', 'tipo']),
            models.Index(fields=['cuenta', 'fecha']),
            models.Index(fields=['cuenta_corriente', 'fecha']),
        ]

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


class TipoCambioMensual(TimeStampedModel):
    """
    Coeficiente de conversión mensual fijado para convertir Pesos Argentinos (ARS) a Dólares (USD)
    o viceversa, permitiendo comparabilidad histórica y presupuestaria en la gestión olivícola.
    """
    class Mes(models.IntegerChoices):
        ENERO = 1, _('Enero')
        FEBRERO = 2, _('Febrero')
        MARZO = 3, _('Marzo')
        ABRIL = 4, _('Abril')
        MAYO = 5, _('Mayo')
        JUNIO = 6, _('Junio')
        JULIO = 7, _('Julio')
        AGOSTO = 8, _('Agosto')
        SEPTIEMBRE = 9, _('Septiembre')
        OCTUBRE = 10, _('Octubre')
        NOVIEMBRE = 11, _('Noviembre')
        DICIEMBRE = 12, _('Diciembre')

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='tipos_cambio',
        verbose_name=_("Empresa")
    )
    ano = models.PositiveSmallIntegerField(verbose_name=_("Año"))
    mes = models.PositiveSmallIntegerField(choices=Mes.choices, verbose_name=_("Mes"))
    tc = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1050.00"),
        verbose_name=_("Tipo de Cambio Oficial (ARS por USD)")
    )
    fuente = models.CharField(
        max_length=120,
        blank=True,
        default="Banco Nación (BNA) / Oficial",
        verbose_name=_("Fuente / Observaciones")
    )

    class Meta:
        verbose_name = _("Tipo de Cambio Mensual")
        verbose_name_plural = _("Tipos de Cambio Mensuales")
        unique_together = [['empresa', 'ano', 'mes']]
        ordering = ['-ano', '-mes']

    def __str__(self):
        return f"{self.get_mes_display()} {self.ano}: $1 USD = ${self.tc:,.2f} ARS"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalidar caché al actualizar tipos de cambio
        cache.clear()

    @classmethod
    def get_tc(cls, empresa=None, ano=None, mes=None, default=Decimal("1050.00")):
        """Obtiene el tipo de cambio oficial para el año y mes dados, con fallback robusto y caché en memoria."""
        if not ano or not mes:
            from django.utils import timezone
            now = timezone.now()
            ano = ano or now.year
            mes = mes or now.month
        
        empresa_id = empresa.id if hasattr(empresa, 'id') else empresa
        cache_key = f"tc_mensual_{empresa_id}_{ano}_{mes}"
        cached_val = cache.get(cache_key)
        if cached_val is not None:
            return cached_val
        
        qs = cls.objects.all()
        if empresa:
            qs = qs.filter(empresa=empresa)
            
        exact = qs.filter(ano=ano, mes=mes).first()
        if exact and exact.tc > 0:
            res = exact.tc
        else:
            prev = qs.filter(models.Q(ano__lt=ano) | models.Q(ano=ano, mes__lte=mes)).order_by('-ano', '-mes').first()
            if prev and prev.tc > 0:
                res = prev.tc
            else:
                latest = qs.order_by('-ano', '-mes').first()
                if latest and latest.tc > 0:
                    res = latest.tc
                else:
                    res = default

        cache.set(cache_key, res, timeout=600)
        return res


class CuadroResultado(TimeStampedModel):
    """Estado de Resultados / Cuadro de Resultados estructurado por período para la gerencia y directorio."""
    class TipoPeriodo(models.TextChoices):
        MENSUAL = 'MENSUAL', _('Mensual')
        TRIMESTRAL = 'TRIMESTRAL', _('Trimestral')
        SEMESTRAL = 'SEMESTRAL', _('Semestral')
        CAMPANA_ANUAL = 'CAMPANA_ANUAL', _('Campaña Anual Olivícola')
        PERSONALIZADO = 'PERSONALIZADO', _('Período Personalizado')

    class Moneda(models.TextChoices):
        ARS = 'ARS', _('Pesos Argentinos (ARS)')
        USD = 'USD', _('Dólares Estadounidenses (USD)')

    class EstadoCuadro(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador (En Armado)')
        REVISION_GERENCIA = 'REVISION', _('En Revisión de Gerencia')
        APROBADO_DIRECTORIO = 'APROBADO', _('Aprobado por Directorio')

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='cuadros_resultado', verbose_name=_("Empresa"))
    titulo = models.CharField(max_length=180, verbose_name=_("Título del Cuadro / Informe"))
    tipo_periodo = models.CharField(max_length=20, choices=TipoPeriodo.choices, default=TipoPeriodo.CAMPANA_ANUAL, verbose_name=_("Tipo de Período"))
    fecha_inicio = models.DateField(verbose_name=_("Fecha Desde"))
    fecha_fin = models.DateField(verbose_name=_("Fecha Hasta"))
    moneda = models.CharField(max_length=5, choices=Moneda.choices, default=Moneda.ARS, verbose_name=_("Moneda de Presentación"))
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000, verbose_name=_("Tipo de Cambio Oficial (ARS/USD)"))
    estado = models.CharField(max_length=20, choices=EstadoCuadro.choices, default=EstadoCuadro.BORRADOR, verbose_name=_("Estado"))
    
    # Parámetros operativos del período (para análisis unitario de costos y márgenes)
    volumen_aceituna_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Aceituna Cosechada / Molida (Kg)"))
    volumen_aceite_litros = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Aceite Elaborado (Litros)"))
    
    # Análisis y notas gerenciales
    notas_gerencia = models.TextField(blank=True, verbose_name=_("Análisis y Conclusiones para la Gerencia"), help_text=_("Comentarios de rendimiento, calidad, precios de exportación y desvíos."))

    # Subtotales e indicadores consolidados en caché
    ventas_totales = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Ventas Netas Totales"))
    costo_produccion = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Costo de Mercaderías Vendidas / Producción"))
    margen_bruto = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Margen Bruto (Utilidad Bruta)"))
    gastos_administracion = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Gastos de Administración"))
    gastos_comercializacion = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Gastos de Comercialización y Exportación"))
    ebitda = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Resultado Operativo (EBITDA)"))
    amortizaciones = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Amortizaciones y Depreciaciones"))
    resultados_financieros = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Resultados Financieros y por Tenencia"))
    impuestos = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Impuesto a las Ganancias y Tasas"))
    resultado_neto = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Resultado Neto del Ejercicio"))

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Usuario Responsable")
    )

    class Meta:
        verbose_name = _("Cuadro de Resultados")
        verbose_name_plural = _("Cuadros de Resultados")
        ordering = ['-fecha_fin', '-created_at']

    def __str__(self):
        return f"{self.titulo} ({self.fecha_inicio} al {self.fecha_fin}) - {self.get_estado_display()}"

    @property
    def margen_bruto_pct(self):
        if self.ventas_totales and self.ventas_totales > 0:
            return round((self.margen_bruto / self.ventas_totales) * 100, 1)
        return 0.0

    @property
    def margen_ebitda_pct(self):
        if self.ventas_totales and self.ventas_totales > 0:
            return round((self.ebitda / self.ventas_totales) * 100, 1)
        return 0.0

    @property
    def margen_neto_pct(self):
        if self.ventas_totales and self.ventas_totales > 0:
            return round((self.resultado_neto / self.ventas_totales) * 100, 1)
        return 0.0

    @property
    def costo_unitario_kg_aceituna(self):
        if self.volumen_aceituna_kg and self.volumen_aceituna_kg > 0:
            return round(self.costo_produccion / self.volumen_aceituna_kg, 2)
        return 0.0

    @property
    def costo_unitario_litro_aceite(self):
        if self.volumen_aceite_litros and self.volumen_aceite_litros > 0:
            return round(self.costo_produccion / self.volumen_aceite_litros, 2)
        return 0.0

    def recalcular_totales(self, save=True):
        """Recalcula todos los márgenes y subtotales en cascada a partir de sus líneas."""
        from decimal import Decimal
        lineas = list(self.lineas.all())
        
        vt = Decimal('0')
        cp = Decimal('0')
        ga = Decimal('0')
        gc = Decimal('0')
        am = Decimal('0')
        rf = Decimal('0')
        imp = Decimal('0')
        ext = Decimal('0')

        for l in lineas:
            m = l.monto_real or Decimal('0')
            sec = l.seccion
            if sec == LineaCuadroResultado.SeccionResultado.INGRESOS_OPERATIVOS:
                vt += m
            elif sec in [
                LineaCuadroResultado.SeccionResultado.COSTOS_PRODUCCION_AGRO,
                LineaCuadroResultado.SeccionResultado.COSTOS_PRODUCCION_IND,
                LineaCuadroResultado.SeccionResultado.COSTOS_ENVASADO,
                LineaCuadroResultado.SeccionResultado.COSTOS_VENTAS,
            ]:
                cp += m
            elif sec == LineaCuadroResultado.SeccionResultado.GASTOS_ADMIN:
                ga += m
            elif sec == LineaCuadroResultado.SeccionResultado.GASTOS_COMERCIALIZACION:
                gc += m
            elif sec == LineaCuadroResultado.SeccionResultado.AMORTIZACIONES:
                am += m
            elif sec == LineaCuadroResultado.SeccionResultado.RESULTADOS_FINANCIEROS:
                # Si es saldo deudor es pérdida (-), si es acreedor es ganancia (+)
                rf += m
            elif sec == LineaCuadroResultado.SeccionResultado.IMPUESTOS:
                imp += m
            elif sec == LineaCuadroResultado.SeccionResultado.EXTRAORDINARIOS:
                ext += m

        self.ventas_totales = vt
        self.costo_produccion = cp
        self.margen_bruto = vt - cp
        self.gastos_administracion = ga
        self.gastos_comercializacion = gc
        self.ebitda = self.margen_bruto - (ga + gc)
        self.amortizaciones = am
        self.resultados_financieros = rf
        self.impuestos = imp
        self.resultado_neto = self.ebitda - am + rf - imp + ext

        if save:
            self.save()

        # Recalcular porcentajes verticales y desvíos en cada línea
        for l in lineas:
            changed = False
            m = l.monto_real or Decimal('0')
            presup = l.monto_presupuestado or Decimal('0')
            
            # % sobre ventas
            if vt > 0:
                pct = round((m / vt) * 100, 2)
            else:
                pct = Decimal('0')
            if l.porcentaje_ventas != pct:
                l.porcentaje_ventas = pct
                changed = True
                
            # Desvío
            desv_m = m - presup
            if l.desvio_monto != desv_m:
                l.desvio_monto = desv_m
                changed = True
                
            if presup > 0:
                desv_p = round((desv_m / presup) * 100, 1)
            else:
                desv_p = Decimal('0')
            if l.desvio_porcentaje != desv_p:
                l.desvio_porcentaje = desv_p
                changed = True

            if changed:
                l.save(update_fields=['porcentaje_ventas', 'desvio_monto', 'desvio_porcentaje'])


class LineaCuadroResultado(TimeStampedModel):
    """Detalle de cuenta contable imputada dentro del Estado de Resultados."""
    class SeccionResultado(models.TextChoices):
        INGRESOS_OPERATIVOS = 'INGRESOS_OPERATIVOS', _('1. Ingresos Operativos (Ventas Netas)')
        COSTOS_PRODUCCION_AGRO = 'COSTOS_PROD_AGRO', _('2.1 Costos de Producción Agrícola (Campo)')
        COSTOS_PRODUCCION_IND = 'COSTOS_PROD_IND', _('2.2 Costos Industriales (Almazara/Extracción)')
        COSTOS_ENVASADO = 'COSTOS_ENVASADO', _('2.3 Costos de Envasado, Tapas y Etiquetas')
        COSTOS_VENTAS = 'COSTOS_VENTAS', _('2.4 Otros Costos de Ventas')
        GASTOS_ADMIN = 'GASTOS_ADMIN', _('3.1 Gastos de Administración y Estructura')
        GASTOS_COMERCIALIZACION = 'GASTOS_COMERCIALIZACION', _('3.2 Gastos Comerciales, Logística y Exportación')
        AMORTIZACIONES = 'AMORTIZACIONES', _('4. Amortizaciones y Depreciaciones')
        RESULTADOS_FINANCIEROS = 'RESULTADOS_FINANCIEROS', _('5. Resultados Financieros y por Tenencia (NIC 41)')
        IMPUESTOS = 'IMPUESTOS', _('6. Impuesto a las Ganancias y Tasas')
        EXTRAORDINARIOS = 'EXTRAORDINARIOS', _('7. Resultados Extraordinarios')

    cuadro = models.ForeignKey(
        CuadroResultado,
        on_delete=models.CASCADE,
        related_name='lineas',
        verbose_name=_("Cuadro de Resultados")
    )
    cuenta_contable = models.ForeignKey(
        CuentaContable,
        on_delete=models.PROTECT,
        related_name='lineas_cuadro_resultado',
        verbose_name=_("Cuenta Contable Asociada")
    )
    seccion = models.CharField(
        max_length=30,
        choices=SeccionResultado.choices,
        default=SeccionResultado.INGRESOS_OPERATIVOS,
        verbose_name=_("Sección del Estado de Resultados")
    )
    monto_real = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Importe Real ($)"))
    monto_presupuestado = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Presupuesto ($)"))
    porcentaje_ventas = models.DecimalField(max_digits=6, decimal_places=2, default=0.00, verbose_name=_("% s/ Ventas"))
    desvio_monto = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Desvío ($)"))
    desvio_porcentaje = models.DecimalField(max_digits=6, decimal_places=2, default=0.00, verbose_name=_("Desvío (%)"))
    observaciones = models.CharField(max_length=255, blank=True, verbose_name=_("Observaciones de la Línea"))

    class Meta:
        verbose_name = _("Línea de Cuadro de Resultados")
        verbose_name_plural = _("Líneas de Cuadro de Resultados")
        ordering = ['seccion', 'cuenta_contable__codigo']
        unique_together = [['cuadro', 'cuenta_contable']]

    def __str__(self):
        return f"{self.cuenta_contable.codigo} {self.cuenta_contable.nombre}: ${self.monto_real:,.2f}"


# ──────────────────────────────────────────────────────────────────────────────
# MÓDULO DE FACTURACIÓN Y LIBRO DE IVA (COMPRAS Y VENTAS)
# ──────────────────────────────────────────────────────────────────────────────

class ComprobanteFiscal(TimeStampedModel):
    """Comprobantes fiscales de compras y ventas para Cuentas por Pagar/Cobrar y Libro de IVA."""
    class TipoOperacion(models.TextChoices):
        COMPRA = 'COMPRA', _('Compra (Crédito Fiscal / Cta. a Pagar)')
        VENTA = 'VENTA', _('Venta (Débito Fiscal / Cta. a Cobrar)')

    class TipoComprobante(models.TextChoices):
        FACTURA_A = 'F_A', _('Factura A')
        FACTURA_B = 'F_B', _('Factura B')
        FACTURA_C = 'F_C', _('Factura C')
        FACTURA_M = 'F_M', _('Factura M')
        NOTA_DEBITO_A = 'ND_A', _('Nota de Débito A')
        NOTA_DEBITO_B = 'ND_B', _('Nota de Débito B')
        NOTA_DEBITO_C = 'ND_C', _('Nota de Débito C')
        NOTA_CREDITO_A = 'NC_A', _('Nota de Crédito A')
        NOTA_CREDITO_B = 'NC_B', _('Nota de Crédito B')
        NOTA_CREDITO_C = 'NC_C', _('Nota de Crédito C')
        RECIBO_OFICIAL = 'REC_OF', _('Recibo Oficial / Recibo X')
        COMPROBANTE_INTERNO_X = 'COMP_X', _('Comprobante Interno (No Fiscal)')
        PRESUPUESTO = 'PRESUP', _('Presupuesto / Proforma')
        REMITO_INTERNO = 'REM_INT', _('Remito Valorizado')

    class CondicionIVA(models.TextChoices):
        RESPONSABLE_INSCRIPTO = 'RI', _('IVA Responsable Inscripto')
        MONOTRIBUTO = 'MONO', _('Responsable Monotributo')
        EXENTO = 'EXENTO', _('IVA Exento')
        CONSUMIDOR_FINAL = 'CF', _('Consumidor Final')

    class EstadoPago(models.TextChoices):
        PENDIENTE = 'PENDIENTE', _('Pendiente de Pago / Cobro')
        PAGO_PARCIAL = 'PARCIAL', _('Pago Parcial')
        PAGADA = 'PAGADA', _('Cancelada / Pagada Total')
        ANULADA = 'ANULADA', _('Anulada')

    tipo_operacion = models.CharField(max_length=10, choices=TipoOperacion.choices, default=TipoOperacion.COMPRA, verbose_name=_("Tipo de Operación"))
    tipo_comprobante = models.CharField(max_length=10, choices=TipoComprobante.choices, default=TipoComprobante.FACTURA_A, verbose_name=_("Tipo de Comprobante"))
    punto_de_venta = models.CharField(max_length=5, default="00001", verbose_name=_("Punto de Venta (PV)"))
    numero_comprobante = models.CharField(max_length=8, verbose_name=_("Número de Comprobante"))
    
    es_oficial = models.BooleanField(default=True, verbose_name=_("Registro Oficial (ARCA/AFIP)"), help_text=_("Indica si es factura oficial (Blanco) o interna (Negro/2)"))

    
    fecha_emision = models.DateField(verbose_name=_("Fecha de Emisión"))
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name=_("Fecha de Vencimiento"))

    cuenta_corriente = models.ForeignKey(
        CuentaCorriente,
        on_delete=models.PROTECT,
        related_name='comprobantes_fiscales',
        verbose_name=_("Proveedor / Cliente"),
        help_text=_("Entidad de la cuenta corriente vinculada.")
    )
    razon_social = models.CharField(max_length=200, verbose_name=_("Razón Social / Nombre"))
    cuit = models.CharField(max_length=20, verbose_name=_("CUIT / Identificación Tributaria"))
    condicion_iva = models.CharField(max_length=10, choices=CondicionIVA.choices, default=CondicionIVA.RESPONSABLE_INSCRIPTO, verbose_name=_("Condición Frente al IVA"))

    concepto = models.CharField(max_length=255, verbose_name=_("Concepto / Descripción"))

    # Desglose impositivo argentino para Libro de IVA
    neto_gravado_21 = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Neto Gravado 21%"))
    neto_gravado_10_5 = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Neto Gravado 10.5%"))
    neto_gravado_27 = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Neto Gravado 27%"))
    
    iva_21 = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("IVA Liquidado 21%"))
    iva_10_5 = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("IVA Liquidado 10.5%"))
    iva_27 = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("IVA Liquidado 27%"))

    no_gravado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Conceptos No Gravados"))
    exento = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Operaciones Exentas"))
    
    percepcion_iva = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Percepción de IVA"))
    percepcion_iibb = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Percepción IIBB (Catamarca / CM)"))
    impuestos_internos = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Impuestos Internos / Otros"))

    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Importe Total Facturado"))

    # Estado de Cuentas por Pagar / Cobrar
    estado_pago = models.CharField(max_length=15, choices=EstadoPago.choices, default=EstadoPago.PENDIENTE, verbose_name=_("Estado de Pago"))
    saldo_pendiente = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Saldo Pendiente"))

    # AFIP / ARCA
    cae = models.CharField(max_length=25, blank=True, verbose_name=_("CAE / CAI"))
    vto_cae = models.DateField(null=True, blank=True, verbose_name=_("Vencimiento CAE"))

    # Vinculación contable opcional
    cuenta_contable = models.ForeignKey(
        CuentaContable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comprobantes_fiscales',
        verbose_name=_("Cuenta Contable Imputable")
    )
    centro_de_costo = models.ForeignKey(
        CentroDeCosto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comprobantes_fiscales',
        verbose_name=_("Centro de Costo")
    )

    class Meta:
        verbose_name = _("Comprobante Fiscal")
        verbose_name_plural = _("Comprobantes Fiscales (Libro IVA)")
        ordering = ['-fecha_emision', '-id']
        unique_together = [['tipo_operacion', 'tipo_comprobante', 'punto_de_venta', 'numero_comprobante', 'cuit']]
        indexes = [
            models.Index(fields=['fecha_emision', 'tipo_operacion']),
            models.Index(fields=['cuenta_corriente', 'estado_pago']),
            models.Index(fields=['estado_pago', 'fecha_vencimiento']),
        ]

    def __str__(self):
        return f"{self.get_tipo_comprobante_display()} {self.punto_de_venta}-{self.numero_comprobante} ({self.razon_social}) - ${self.total:,.2f}"

    @property
    def total_iva(self):
        return (self.iva_21 or Decimal('0')) + (self.iva_10_5 or Decimal('0')) + (self.iva_27 or Decimal('0'))

    @property
    def numero_completo(self):
        return f"{str(self.punto_de_venta).zfill(5)}-{str(self.numero_comprobante).zfill(8)}"


# ──────────────────────────────────────────────────────────────────────────────
# MÓDULO DE ARQUEO DE CAJA DIARIO
# ──────────────────────────────────────────────────────────────────────────────

class ArqueoCaja(TimeStampedModel):
    """Arqueo y cierre diario de caja chica / efectivo en finca o administración."""
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador (En Conteo)')
        CERRADO = 'CERRADO', _('Arqueo Cerrado y Validado')

    cuenta = models.ForeignKey(
        Cuenta,
        on_delete=models.PROTECT,
        limit_choices_to={'tipo': 'CAJA_EFECTIVO'},
        related_name='arqueos',
        verbose_name=_("Caja Física")
    )
    fecha = models.DateField(verbose_name=_("Fecha de Corte / Cierre"))
    hora = models.TimeField(verbose_name=_("Hora de Arqueo"))
    saldo_sistema = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Saldo según Sistema (ARS)"))
    saldo_real_contado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Efectivo Contado Físicamente (ARS)"))
    diferencia = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Diferencia (+ Sobrante / - Faltante)"))
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.CERRADO, verbose_name=_("Estado"))
    observaciones = models.TextField(blank=True, verbose_name=_("Observaciones / Justificación"))
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Responsable del Cierre")
    )

    class Meta:
        verbose_name = _("Arqueo de Caja")
        verbose_name_plural = _("Arqueos de Caja")
        ordering = ['-fecha', '-hora']

    def __str__(self):
        return f"Arqueo {self.cuenta.nombre} al {self.fecha} {self.hora} (Dif: ${self.diferencia:,.2f})"

    def save(self, *args, **kwargs):
        self.diferencia = self.saldo_real_contado - self.saldo_sistema
        super().save(*args, **kwargs)


# ──────────────────────────────────────────────────────────────────────────────
# MÓDULO DE ÓRDENES DE PAGO Y RECIBOS DE COBRANZA
# ──────────────────────────────────────────────────────────────────────────────

class OrdenPagoRecibo(TimeStampedModel):
    """Órdenes de pago formales a proveedores y recibos de cobranza de clientes."""
    class TipoDocumento(models.TextChoices):
        ORDEN_PAGO = 'OP', _('Orden de Pago (a Proveedor)')
        RECIBO_COBRANZA = 'RC', _('Recibo de Cobranza (de Cliente)')

    class MedioPago(models.TextChoices):
        EFECTIVO = 'EFECTIVO', _('Efectivo (Caja Chica)')
        TRANSFERENCIA = 'TRANSFERENCIA', _('Transferencia Bancaria')
        CHEQUE_PROPIO = 'CHEQUE_PROPIO', _('Cheque Propio Emitido')
        CHEQUE_TERCERO = 'CHEQUE_TERCERO', _('Cheque de Tercero (Cartera)')

    tipo = models.CharField(max_length=5, choices=TipoDocumento.choices, default=TipoDocumento.ORDEN_PAGO, verbose_name=_("Tipo de Comprobante"))
    numero = models.CharField(max_length=30, unique=True, verbose_name=_("N° de Orden / Recibo"))
    fecha = models.DateField(verbose_name=_("Fecha de Emisión"))
    
    cuenta_corriente = models.ForeignKey(
        CuentaCorriente,
        on_delete=models.PROTECT,
        related_name='ordenes_y_recibos',
        verbose_name=_("Proveedor / Cliente")
    )
    cuenta_financiera = models.ForeignKey(
        Cuenta,
        on_delete=models.PROTECT,
        related_name='ordenes_y_recibos',
        verbose_name=_("Caja o Cuenta Bancaria")
    )
    importe_total = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Importe Total Abonado/Cobrado"))
    medio_pago = models.CharField(max_length=20, choices=MedioPago.choices, default=MedioPago.TRANSFERENCIA, verbose_name=_("Medio de Pago"))
    cheque = models.ForeignKey(
        Cheque,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_pago',
        verbose_name=_("Cheque Utilizado (si aplica)")
    )
    comprobante_fiscal = models.ForeignKey(
        ComprobanteFiscal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos_recibos',
        verbose_name=_("Factura Imputada (opcional)")
    )
    movimiento_financiero = models.ForeignKey(
        MovimientoFinanciero,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orden_recibo_origen',
        verbose_name=_("Movimiento de Tesorería Generado")
    )
    concepto = models.CharField(max_length=255, verbose_name=_("Concepto / Motivo"))
    beneficiario_firmante = models.CharField(max_length=150, blank=True, verbose_name=_("Beneficiario / Quien Recibe"))
    dni_firmante = models.CharField(max_length=30, blank=True, verbose_name=_("DNI / CUIT de Quien Recibe"))
    observaciones = models.TextField(blank=True, verbose_name=_("Observaciones"))
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Emitido por")
    )

    class Meta:
        verbose_name = _("Orden de Pago / Recibo")
        verbose_name_plural = _("Órdenes de Pago y Recibos")
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"{self.get_tipo_display()} {self.numero} - {self.cuenta_corriente.razon_social} (${self.importe_total:,.2f})"

