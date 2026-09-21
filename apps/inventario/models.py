from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel, Finca

class CategoriaInsumo(TimeStampedModel):
    """Categoría para clasificar insumos agropecuarios y de fábrica."""
    nombre = models.CharField(max_length=80, unique=True, verbose_name=_("Nombre de Categoría"))
    descripcion = models.TextField(blank=True, verbose_name=_("Descripción"))
    cuenta_contable_activo = models.ForeignKey(
        'finanzas.CuentaContable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='categorias_insumo_activo',
        verbose_name=_("Cuenta Contable de Existencias (Activo)")
    )
    cuenta_contable_gasto = models.ForeignKey(
        'finanzas.CuentaContable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='categorias_insumo_gasto',
        verbose_name=_("Cuenta Contable de Consumo/Gasto")
    )

    class Meta:
        verbose_name = _("Categoría de Insumo")
        verbose_name_plural = _("Categorías de Insumos")
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Deposito(TimeStampedModel):
    """Depósito físico de almacenamiento de insumos en cada finca o nave central."""
    finca = models.ForeignKey(Finca, on_delete=models.CASCADE, related_name='depositos', verbose_name=_("Finca"))
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre del Depósito"))
    codigo = models.CharField(max_length=30, unique=True, verbose_name=_("Código Interno"))
    es_deposito_central = models.BooleanField(default=False, verbose_name=_("¿Es Depósito Central?"))
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))

    class Meta:
        verbose_name = _("Depósito")
        verbose_name_plural = _("Depósitos")
        ordering = ['finca', 'nombre']

    def __str__(self):
        return f"{self.nombre} - {self.finca.nombre}"


class Insumo(TimeStampedModel):
    """Artículos e insumos agrícolas (agroquímicos, fertilizantes, combustibles, envases)."""
    class UnidadMedida(models.TextChoices):
        LITROS = 'LTS', _('Litros (Lts)')
        KILOS = 'KG', _('Kilogramos (Kg)')
        GRAMOS = 'GRS', _('Gramos (Grs)')
        UNIDADES = 'UNIDAD', _('Unidad')
        BINS = 'BINS', _('Bins de Cosecha')
        BOLSAS = 'BOLSA', _('Bolsas / Sacos')
        METROS_CUBICOS = 'M3', _('Metros Cúbicos')

    codigo = models.CharField(max_length=40, unique=True, verbose_name=_("Código Insumo"))
    nombre = models.CharField(max_length=150, verbose_name=_("Nombre del Insumo / Producto"))
    categoria = models.ForeignKey(
        CategoriaInsumo, 
        on_delete=models.PROTECT, 
        related_name='insumos', 
        verbose_name=_("Categoría")
    )
    unidad_medida = models.CharField(
        max_length=20, 
        choices=UnidadMedida.choices, 
        default=UnidadMedida.LITROS, 
        verbose_name=_("Unidad de Medida")
    )
    principio_activo = models.CharField(max_length=120, blank=True, verbose_name=_("Principio Activo / Composición"))
    stock_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Stock Total Global"))
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, verbose_name=_("Stock Mínimo de Alerta"))
    costo_unitario_ars = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00, 
        verbose_name=_("Costo Unitario PPP (ARS)"),
        help_text=_("Precio Promedio Ponderado en ARS")
    )
    costo_unitario_usd = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        verbose_name=_("Costo Unitario PPP (USD)")
    )
    cuenta_contable = models.ForeignKey(
        'finanzas.CuentaContable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='insumos_vinculados',
        verbose_name=_("Cuenta Contable Específica"),
        help_text=_("Opcional: Si no se especifica, toma las cuentas de su categoría.")
    )
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))

    class Meta:
        verbose_name = _("Insumo")
        verbose_name_plural = _("Insumos")
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.get_unidad_medida_display()})"

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo

    @property
    def valor_total_stock_ars(self):
        return round(self.stock_actual * self.costo_unitario_ars, 2)


class StockPorDeposito(TimeStampedModel):
    """Cantidad de existencias de un insumo en un depósito específico."""
    deposito = models.ForeignKey(Deposito, on_delete=models.CASCADE, related_name='existencias', verbose_name=_("Depósito"))
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, related_name='existencias_por_deposito', verbose_name=_("Insumo"))
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Cantidad en Depósito"))

    class Meta:
        verbose_name = _("Existencia por Depósito")
        verbose_name_plural = _("Existencias por Depósito")
        unique_together = ('deposito', 'insumo')

    def __str__(self):
        return f"{self.insumo.nombre} en {self.deposito.nombre}: {self.cantidad} {self.insumo.unidad_medida}"


class MovimientoStock(TimeStampedModel):
    """Auditoría y trazabilidad estricta de todo movimiento de inventario."""
    class TipoMovimiento(models.TextChoices):
        ENTRADA_COMPRA = 'ENTRADA_COMPRA', _('Entrada por Compra / Remito')
        SALIDA_PARTE_DIARIO = 'SALIDA_PARTE_DIARIO', _('Salida por Parte Diario / Cuadro')
        TRANSFERENCIA = 'TRANSFERENCIA', _('Transferencia entre Depósitos')
        AJUSTE_POSITIVO = 'AJUSTE_POSITIVO', _('Ajuste de Inventario (+)')
        AJUSTE_NEGATIVO = 'AJUSTE_NEGATIVO', _('Ajuste de Inventario (-)')
        SALIDA_MERMA = 'SALIDA_MERMA', _('Merma / Vencimiento')

    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='movimientos', verbose_name=_("Insumo"))
    deposito = models.ForeignKey(Deposito, on_delete=models.PROTECT, related_name='movimientos_origen', verbose_name=_("Depósito Origen"))
    deposito_destino = models.ForeignKey(
        Deposito, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='movimientos_destino_transferencia', 
        verbose_name=_("Depósito Destino (si es transf.)")
    )
    tipo = models.CharField(max_length=30, choices=TipoMovimiento.choices, verbose_name=_("Tipo de Movimiento"))
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Cantidad"))
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Costo Unitario al Movimiento"))
    fecha = models.DateTimeField(verbose_name=_("Fecha y Hora del Movimiento"))
    motivo = models.CharField(max_length=200, verbose_name=_("Motivo / Concepto"))
    referencia_origen = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name=_("Documento de Referencia"),
        help_text=_("ID Parte Diario, N° Remito o Factura")
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name=_("Usuario Registrador")
    )

    class Meta:
        verbose_name = _("Movimiento de Stock")
        verbose_name_plural = _("Movimientos de Stock")
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.insumo.nombre} ({self.cantidad} {self.insumo.unidad_medida})"

    @property
    def costo_total_movimiento(self):
        return round(self.cantidad * self.costo_unitario, 2)


class Maquina(TimeStampedModel):
    """Parque de maquinaria, tractores y atomizadoras de la empresa olivícola."""
    class TipoMaquina(models.TextChoices):
        TRACTOR = 'TRACTOR', _('Tractor Agrícola')
        COSECHADORA_VIBRADORA = 'COSECHADORA', _('Cosechadora Vibradora de Tronco')
        ATOMIZADORA = 'ATOMIZADORA', _('Atomizadora / Pulverizadora')
        DESMALEZADORA = 'DESMALEZADORA', _('Desmalezadora / Rastra')
        CAMION = 'CAMION', _('Camión / Transporte')
        CAMIONETA = 'CAMIONETA', _('Camioneta / Utilitario')
        OTRO = 'OTRO', _('Otro Equipo')

    class EstadoMaquina(models.TextChoices):
        OPERATIVA = 'OPERATIVA', _('Operativa')
        EN_MANTENIMIENTO = 'EN_MANTENIMIENTO', _('En Taller / Mantenimiento')
        FUERA_DE_SERVICIO = 'FUERA_DE_SERVICIO', _('Fuera de Servicio')
        BAJA = 'BAJA', _('Dada de Baja')

    codigo = models.CharField(max_length=30, unique=True, verbose_name=_("Código Maquinaria"))
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre / Modelo"))
    tipo = models.CharField(max_length=30, choices=TipoMaquina.choices, default=TipoMaquina.TRACTOR, verbose_name=_("Tipo"))
    marca = models.CharField(max_length=60, verbose_name=_("Marca"))
    modelo = models.CharField(max_length=60, blank=True, verbose_name=_("Modelo"))
    ano_fabricacion = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Año de Fabricación"))
    horas_o_km_acumulados = models.DecimalField(max_digits=10, decimal_places=1, default=0.0, verbose_name=_("Horas / Km Acumulados"))
    finca_asignada = models.ForeignKey(Finca, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Finca Asignada"))
    estado = models.CharField(max_length=25, choices=EstadoMaquina.choices, default=EstadoMaquina.OPERATIVA, verbose_name=_("Estado"))
    fecha_ultimo_service = models.DateField(null=True, blank=True, verbose_name=_("Fecha Último Mantenimiento"))

    class Meta:
        verbose_name = _("Máquina / Vehículo")
        verbose_name_plural = _("Parque de Maquinarias")
        ordering = ['codigo']

    def __str__(self):
        return f"[{self.codigo}] {self.nombre} ({self.get_tipo_display()})"


class MantenimientoMaquina(TimeStampedModel):
    """Registro de servicios preventivos y correctivos del parque mecánico."""
    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE, related_name='mantenimientos', verbose_name=_("Máquina"))
    fecha = models.DateField(verbose_name=_("Fecha de Mantenimiento"))
    TIPO_CHOICES = [
        ('PREVENTIVO', 'Service Preventivo (Filtros, Aceite)'),
        ('CORRECTIVO', 'Reparación Correctiva / Rotura'),
        ('LUBRICACION', 'Engrase y Revisión General'),
    ]
    tipo = models.CharField(max_length=25, choices=TIPO_CHOICES, default='PREVENTIVO', verbose_name=_("Tipo de Mantenimiento"))
    horas_maquina = models.DecimalField(max_digits=10, decimal_places=1, verbose_name=_("Horas/Km al momento"))
    descripcion = models.TextField(verbose_name=_("Detalle de las tareas realizadas"))
    costo_total_ars = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Costo Total (ARS)"))
    taller_o_proveedor = models.CharField(max_length=120, blank=True, verbose_name=_("Taller / Mecánico Responsable"))

    class Meta:
        verbose_name = _("Mantenimiento de Máquina")
        verbose_name_plural = _("Mantenimientos de Máquinas")
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.maquina.codigo} - {self.fecha} ({self.get_tipo_display()})"


class Remito(TimeStampedModel):
    """Comprobante legal o interno de traslado y recepción de insumos o productos."""
    class TipoRemito(models.TextChoices):
        ENTRADA_PROVEEDOR = 'ENTRADA_PROVEEDOR', _('Entrada desde Proveedor')
        SALIDA_CLIENTE = 'SALIDA_CLIENTE', _('Salida a Cliente / Exportación')
        INTERNO = 'INTERNO', _('Traslado Interno entre Fincas')

    class EstadoRemito(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador')
        CONFIRMADO = 'CONFIRMADO', _('Confirmado / Ingresado')
        ANULADO = 'ANULADO', _('Anulado')

    numero = models.CharField(max_length=50, unique=True, verbose_name=_("Número de Remito"))
    tipo = models.CharField(max_length=30, choices=TipoRemito.choices, verbose_name=_("Tipo de Remito"))
    fecha = models.DateField(verbose_name=_("Fecha de Emisión / Recepción"))
    entidad_nombre = models.CharField(
        max_length=150, 
        blank=True, 
        verbose_name=_("Proveedor / Cliente"),
        help_text=_("Nombre del proveedor remitente o cliente destinatario")
    )
    finca_origen = models.ForeignKey(Finca, on_delete=models.SET_NULL, null=True, blank=True, related_name='remitos_salientes', verbose_name=_("Finca Origen"))
    finca_destino = models.ForeignKey(Finca, on_delete=models.SET_NULL, null=True, blank=True, related_name='remitos_entrantes', verbose_name=_("Finca Destino"))
    estado = models.CharField(max_length=20, choices=EstadoRemito.choices, default=EstadoRemito.BORRADOR, verbose_name=_("Estado"))
    observaciones = models.TextField(blank=True, verbose_name=_("Observaciones"))
    documento_adjunto = models.FileField(upload_to='remitos/', blank=True, null=True, verbose_name=_("Archivo PDF / Foto"))
    
    # ── Datos de Transporte y Recepción Digital con Firma Móvil ─────────────────
    transportista_nombre = models.CharField(max_length=120, blank=True, verbose_name=_("Transportista / Chofer"))
    patente_vehiculo = models.CharField(max_length=25, blank=True, verbose_name=_("Patente / Dominio Vehículo"))
    firma_digital = models.TextField(blank=True, verbose_name=_("Firma Digital (Base64 PNG)"))
    firma_nombre_receptor = models.CharField(max_length=150, blank=True, verbose_name=_("Nombre Receptor"))
    firma_dni_receptor = models.CharField(max_length=30, blank=True, verbose_name=_("DNI / CUIT Receptor"))
    firma_aclaracion = models.CharField(max_length=150, blank=True, verbose_name=_("Cargo / Relación"))
    firma_fecha_hora = models.DateTimeField(null=True, blank=True, verbose_name=_("Fecha y Hora de Firma"))
    firma_geolocalizacion = models.CharField(max_length=100, blank=True, verbose_name=_("Coordenadas GPS"))

    class Meta:
        verbose_name = _("Remito")
        verbose_name_plural = _("Remitos")
        ordering = ['-fecha']

    def __str__(self):
        return f"Remito {self.numero} ({self.get_tipo_display()})"

    @property
    def esta_firmado(self):
        return bool(self.firma_digital)


class ItemRemito(TimeStampedModel):
    """Detalle de ítems contenidos en un remito."""
    remito = models.ForeignKey(Remito, on_delete=models.CASCADE, related_name='items', verbose_name=_("Remito"))
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, verbose_name=_("Insumo"))
    cantidad_declarada = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Cantidad Declarada"))
    cantidad_recibida = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Cantidad Real Recibida"))
    precio_unitario_ars = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Precio Unitario (ARS)"))

    class Meta:
        verbose_name = _("Ítem de Remito")
        verbose_name_plural = _("Ítems de Remito")

    def __str__(self):
        return f"{self.insumo.nombre} ({self.cantidad_recibida} {self.insumo.unidad_medida})"


# ──────────────────────────────────────────────────────────────────────────────
# MÓDULO ÓRDENES DE COMPRA
# ──────────────────────────────────────────────────────────────────────────────

class OrdenDeCompra(TimeStampedModel):
    """Solicitud formal de compra de insumos a un proveedor."""
    class Estado(models.TextChoices):
        BORRADOR   = 'BORRADOR',   _('Borrador')
        APROBADA   = 'APROBADA',   _('Aprobada / Enviada al proveedor')
        RECIBIDA   = 'RECIBIDA',   _('Recibida Totalmente')
        RECIBIDA_PARCIAL = 'RECIBIDA_PARCIAL', _('Recibida Parcialmente')
        ANULADA    = 'ANULADA',    _('Anulada')

    proveedor = models.ForeignKey(
        'finanzas.CuentaCorriente',
        on_delete=models.PROTECT,
        related_name='ordenes_compra',
        limit_choices_to={'tipo_entidad': 'PROVEEDOR'},
        verbose_name=_("Proveedor")
    )
    finca_destino = models.ForeignKey(Finca, on_delete=models.PROTECT, related_name='ordenes_compra', verbose_name=_("Finca Destino"))
    numero = models.CharField(max_length=30, unique=True, verbose_name=_("N° de OC"))
    fecha_emision = models.DateField(verbose_name=_("Fecha de Emisión"))
    fecha_entrega_estimada = models.DateField(null=True, blank=True, verbose_name=_("Fecha Estimada de Entrega"))
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR, verbose_name=_("Estado"))
    # Opción 1: registrar la deuda al aprobar la OC (antes de recibir la factura)
    registrar_deuda_al_aprobar = models.BooleanField(
        default=False,
        verbose_name=_("Registrar deuda al aprobar OC"),
        help_text=_("Si está activo, la deuda se acredita en la cuenta corriente del proveedor al aprobar la OC. Si no, se espera al momento de recepción/factura.")
    )
    observaciones = models.TextField(blank=True, verbose_name=_("Observaciones"))
    total_estimado_ars = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Total Estimado (ARS)"))

    class Meta:
        verbose_name = _("Orden de Compra")
        verbose_name_plural = _("Órdenes de Compra")
        ordering = ['-fecha_emision']

    def __str__(self):
        return f"OC {self.numero} — {self.proveedor.razon_social} ({self.get_estado_display()})"

    def recalcular_total(self):
        total = sum(item.subtotal_ars for item in self.items.all())
        self.total_estimado_ars = total
        self.save(update_fields=['total_estimado_ars', 'updated_at'])


class ItemOrdenDeCompra(TimeStampedModel):
    """Ítem de insumo dentro de una Orden de Compra."""
    orden = models.ForeignKey(OrdenDeCompra, on_delete=models.CASCADE, related_name='items', verbose_name=_("OC"))
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, verbose_name=_("Insumo"))
    cantidad_solicitada = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Cantidad Solicitada"))
    precio_unitario_estimado_ars = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Precio Unitario Est. (ARS)"))

    class Meta:
        verbose_name = _("Ítem de OC")
        verbose_name_plural = _("Ítems de OC")

    def __str__(self):
        return f"{self.insumo.nombre} × {self.cantidad_solicitada}"

    @property
    def subtotal_ars(self):
        return round(self.cantidad_solicitada * self.precio_unitario_estimado_ars, 2)


class RecepcionMercaderia(TimeStampedModel):
    """Recepción física de mercadería contra una Orden de Compra."""
    class Estado(models.TextChoices):
        PENDIENTE   = 'PENDIENTE',   _('Pendiente de Confirmación')
        CONFIRMADA  = 'CONFIRMADA',  _('Confirmada — Stock Impactado')
        ANULADA     = 'ANULADA',     _('Anulada')

    orden = models.ForeignKey(OrdenDeCompra, on_delete=models.PROTECT, related_name='recepciones', verbose_name=_("Orden de Compra"))
    deposito_destino = models.ForeignKey(Deposito, on_delete=models.PROTECT, verbose_name=_("Depósito de Ingreso"))
    fecha_recepcion = models.DateField(verbose_name=_("Fecha de Recepción"))
    numero_remito_proveedor = models.CharField(max_length=60, blank=True, verbose_name=_("N° Remito Proveedor"))
    numero_factura_proveedor = models.CharField(max_length=60, blank=True, verbose_name=_("N° Factura Proveedor"))
    # Opción 2 (alternativa a registrar_deuda_al_aprobar): registrar la deuda al recibir la factura
    registrar_deuda_al_confirmar = models.BooleanField(
        default=True,
        verbose_name=_("Registrar deuda en cta. cte. al confirmar"),
        help_text=_("Si está activo, al confirmar la recepción se actualizará la cuenta corriente del proveedor con el importe real de la factura.")
    )
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Responsable Recepción"))
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE, verbose_name=_("Estado"))
    observaciones = models.TextField(blank=True, verbose_name=_("Observaciones"))
    total_real_ars = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name=_("Total Real Facturado (ARS)"))

    class Meta:
        verbose_name = _("Recepción de Mercadería")
        verbose_name_plural = _("Recepciones de Mercadería")
        ordering = ['-fecha_recepcion']

    def __str__(self):
        return f"Recepción OC {self.orden.numero} — {self.fecha_recepcion} ({self.get_estado_display()})"


class ItemRecepcion(TimeStampedModel):
    """Detalle de cada insumo recibido en una recepción de mercadería."""
    recepcion = models.ForeignKey(RecepcionMercaderia, on_delete=models.CASCADE, related_name='items', verbose_name=_("Recepción"))
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, verbose_name=_("Insumo"))
    cantidad_en_oc = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Cant. en OC"))
    cantidad_recibida = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Cant. Real Recibida"))
    precio_unitario_real_ars = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name=_("Precio Unitario Real (ARS)"))
    movimiento_stock = models.ForeignKey(
        MovimientoStock,
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Movimiento de Stock Generado")
    )

    class Meta:
        verbose_name = _("Ítem de Recepción")
        verbose_name_plural = _("Ítems de Recepción")

    def __str__(self):
        return f"{self.insumo.nombre}: recibido {self.cantidad_recibida}"

    @property
    def subtotal_real_ars(self):
        return round(self.cantidad_recibida * self.precio_unitario_real_ars, 2)
