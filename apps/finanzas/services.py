from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Cuenta, CuentaCorriente, MovimientoFinanciero, CuentaContable

@transaction.atomic
def registrar_movimiento_financiero(
    cuenta: Cuenta,
    tipo: str,
    fecha,
    importe: Decimal,
    concepto: str,
    moneda: str = 'ARS',
    tipo_cambio: Decimal = Decimal('1.0000'),
    comprobante_tipo: str = '',
    comprobante_nro: str = '',
    cuenta_corriente: CuentaCorriente = None,
    centro_de_costo = None,
    finca = None,
    cuenta_destino: Cuenta = None,
    usuario = None
) -> MovimientoFinanciero:
    """
    Servicio transaccional para asentar un movimiento financiero.
    Actualiza atómicamente el saldo de la Cuenta y la CuentaCorriente vinculada.
    """
    if importe <= 0:
        raise ValidationError("El importe del movimiento debe ser superior a cero.")

    cuenta = Cuenta.objects.select_for_update().get(pk=cuenta.pk)

    if tipo == MovimientoFinanciero.TipoMovimiento.EGRESO:
        cuenta.saldo_actual -= importe
    elif tipo == MovimientoFinanciero.TipoMovimiento.INGRESO:
        cuenta.saldo_actual += importe
    elif tipo == MovimientoFinanciero.TipoMovimiento.TRANSFERENCIA:
        if not cuenta_destino:
            raise ValidationError("Debe especificar una cuenta destino para transferencias.")
        cuenta_destino = Cuenta.objects.select_for_update().get(pk=cuenta_destino.pk)
        cuenta.saldo_actual -= importe
        cuenta_destino.saldo_actual += importe
        cuenta_destino.save(update_fields=['saldo_actual', 'updated_at'])
    else:
        raise ValidationError(f"Tipo de movimiento no válido: {tipo}")

    cuenta.save(update_fields=['saldo_actual', 'updated_at'])

    # Impacto en Cuenta Corriente
    if cuenta_corriente:
        cuenta_corriente = CuentaCorriente.objects.select_for_update().get(pk=cuenta_corriente.pk)
        if cuenta_corriente.tipo_entidad == CuentaCorriente.TipoEntidad.PROVEEDOR:
            # Si le pagamos a un proveedor (EGRESO de nuestra caja), disminuye nuestra deuda (saldo sube hacia 0)
            if tipo == MovimientoFinanciero.TipoMovimiento.EGRESO:
                cuenta_corriente.saldo_actual += importe
            elif tipo == MovimientoFinanciero.TipoMovimiento.INGRESO:
                # Nota de crédito recibida o devolución
                cuenta_corriente.saldo_actual -= importe
        elif cuenta_corriente.tipo_entidad == CuentaCorriente.TipoEntidad.CLIENTE:
            # Si cobramos a un cliente (INGRESO a nuestra caja), cancela su saldo a favor de cobrar
            if tipo == MovimientoFinanciero.TipoMovimiento.INGRESO:
                cuenta_corriente.saldo_actual -= importe
            elif tipo == MovimientoFinanciero.TipoMovimiento.EGRESO:
                # Devolución o anticipo a cliente
                cuenta_corriente.saldo_actual += importe
        cuenta_corriente.save(update_fields=['saldo_actual', 'updated_at'])

    movimiento = MovimientoFinanciero.objects.create(
        cuenta=cuenta,
        cuenta_destino=cuenta_destino,
        tipo=tipo,
        fecha=fecha,
        importe=importe,
        moneda=moneda,
        tipo_cambio=tipo_cambio,
        concepto=concepto,
        comprobante_tipo=comprobante_tipo,
        comprobante_nro=comprobante_nro,
        cuenta_corriente=cuenta_corriente,
        centro_de_costo=centro_de_costo,
        finca=finca,
        usuario=usuario
    )
    return movimiento


def determinar_seccion_cuenta(cuenta: CuentaContable) -> str:
    """Mapea una cuenta contable a su sección en el Cuadro de Resultados."""
    from .models import LineaCuadroResultado
    codigo = cuenta.codigo.strip()
    nombre = (cuenta.nombre or '').lower()

    if 'amortizac' in nombre or 'depreciac' in nombre:
        return LineaCuadroResultado.SeccionResultado.AMORTIZACIONES
    if codigo.startswith('4.1.6') or codigo.startswith('4.2.9'):
        return LineaCuadroResultado.SeccionResultado.EXTRAORDINARIOS
    if codigo.startswith('4.2.7') or codigo in ('4.1.5.03.000000', '4.1.5.04.000000'):
        return LineaCuadroResultado.SeccionResultado.RESULTADOS_FINANCIEROS
    if codigo.startswith('4.2.8'):
        return LineaCuadroResultado.SeccionResultado.IMPUESTOS
    if codigo.startswith('4.1'):
        return LineaCuadroResultado.SeccionResultado.INGRESOS_OPERATIVOS
    if codigo.startswith('4.2.1'):
        return LineaCuadroResultado.SeccionResultado.COSTOS_PRODUCCION_AGRO
    if codigo.startswith('4.2.2'):
        return LineaCuadroResultado.SeccionResultado.COSTOS_PRODUCCION_IND
    if codigo.startswith('4.2.3'):
        return LineaCuadroResultado.SeccionResultado.COSTOS_ENVASADO
    if codigo.startswith('4.2.4'):
        return LineaCuadroResultado.SeccionResultado.COSTOS_VENTAS
    if codigo.startswith('4.2.5'):
        return LineaCuadroResultado.SeccionResultado.GASTOS_ADMIN
    if codigo.startswith('4.2.6'):
        return LineaCuadroResultado.SeccionResultado.GASTOS_COMERCIALIZACION

    if cuenta.clase == CuentaContable.ClaseCuenta.RESULTADO_POSITIVO:
        return LineaCuadroResultado.SeccionResultado.INGRESOS_OPERATIVOS
    return LineaCuadroResultado.SeccionResultado.GASTOS_ADMIN


def poblar_lineas_cuadro(cuadro, inicializar_con_valores_demo: bool = False):
    """
    Puebla un Cuadro de Resultados con todas las cuentas contables imputables de Clase 4 (Resultados).
    Si inicializar_con_valores_demo es True, asigna montos reales y presupuestados realistas de la empresa olivícola.
    """
    from .models import CuentaContable, LineaCuadroResultado
    cuentas_r = CuentaContable.objects.filter(
        codigo__startswith='4.',
        es_imputable=True,
        activa=True
    ).order_by('codigo')

    # Diccionario de valores de referencia para la olivícola (USD)
    valores_demo = {
        # 4.1 Ingresos
        '4.1.1.01': {'real': Decimal('120000'), 'presup': Decimal('110000'), 'obs': 'Venta aceituna fresca a acopiadores locales'},
        '4.1.2.01': {'real': Decimal('220000'), 'presup': Decimal('200000'), 'obs': 'Aceite virgen extra a granel mercado interno'},
        '4.1.2.02': {'real': Decimal('280000'), 'presup': Decimal('260000'), 'obs': 'Aceite embotellado 500ml y 1L distribuidores'},
        '4.1.2.03': {'real': Decimal('480000'), 'presup': Decimal('500000'), 'obs': 'Exportación flexitanks granel a España/EEUU'},
        '4.1.2.04': {'real': Decimal('420000'), 'presup': Decimal('380000'), 'obs': 'Exportación marca propia envasada a Brasil'},
        '4.1.2.05': {'real': Decimal('32000'), 'presup': Decimal('30000'), 'obs': 'Reintegros aduaneros AFIP'},
        '4.1.3.01': {'real': Decimal('65000'), 'presup': Decimal('60000'), 'obs': 'Aceituna Arauco conserva frascos y baldes'},
        '4.1.3.02': {'real': Decimal('45000'), 'presup': Decimal('50000'), 'obs': 'Conservas exportadas'},
        '4.1.4.01': {'real': Decimal('18000'), 'presup': Decimal('15000'), 'obs': 'Venta orujo a extractora de orujo'},
        '4.1.4.02': {'real': Decimal('9000'), 'presup': Decimal('8000'), 'obs': 'Venta carozo/hueso para calderas biomasa'},
        '4.1.5.01': {'real': Decimal('35000'), 'presup': Decimal('30000'), 'obs': 'Servicio molienda a productores vecinos (maquila)'},
        '4.1.5.02': {'real': Decimal('12000'), 'presup': Decimal('10000'), 'obs': 'Alquiler temporario tractor y cosechadora'},
        # 4.2.1 Costo Producción Agrícola
        '4.2.1.01': {'real': Decimal('165000'), 'presup': Decimal('160000'), 'obs': 'Encargados, tractoristas y cuadrilla de campo'},
        '4.2.1.02': {'real': Decimal('115000'), 'presup': Decimal('120000'), 'obs': 'Fertirriego, enmiendas foliares, fitosanitarios'},
        '4.2.1.03': {'real': Decimal('38000'), 'presup': Decimal('40000'), 'obs': 'Cuadrilla poda anual invernal y chipeado'},
        '4.2.1.04': {'real': Decimal('82000'), 'presup': Decimal('78000'), 'obs': 'Mano de obra transitoria cosecha manual arauco'},
        '4.2.1.05': {'real': Decimal('62000'), 'presup': Decimal('65000'), 'obs': 'Contratista cosecha mecánica cabalgante'},
        '4.2.1.06': {'real': Decimal('24000'), 'presup': Decimal('22000'), 'obs': 'Fletes de tolvas y bines desde cuadros a almazara'},
        '4.2.1.07': {'real': Decimal('32000'), 'presup': Decimal('32000'), 'obs': 'Amortización sistema de riego presurizado'},
        # 4.2.2 Costo Producción Industrial
        '4.2.2.01': {'real': Decimal('88000'), 'presup': Decimal('85000'), 'obs': 'Jefe de planta y operarios molienda continua'},
        '4.2.2.02': {'real': Decimal('56000'), 'presup': Decimal('52000'), 'obs': 'Energía eléctrica trifásica pico campaña'},
        '4.2.2.03': {'real': Decimal('28000'), 'presup': Decimal('30000'), 'obs': 'Repuestos decanter, centrífuga, bombas'},
        '4.2.2.04': {'real': Decimal('14000'), 'presup': Decimal('15000'), 'obs': 'Acidez, peróxidos, panel test cata virgen extra'},
        '4.2.2.05': {'real': Decimal('35000'), 'presup': Decimal('35000'), 'obs': 'Amortización línea molienda Pieralisi'},
        # 4.2.3 Costo Envasado y Fraccionado
        '4.2.3.01': {'real': Decimal('38000'), 'presup': Decimal('36000'), 'obs': 'Operarios línea llenado, etiquetado y embalaje'},
        '4.2.3.02': {'real': Decimal('86000'), 'presup': Decimal('80000'), 'obs': 'Botellas vidrio UVAG, tapas irrellenables, etiquetas'},
        '4.2.3.03': {'real': Decimal('12000'), 'presup': Decimal('12000'), 'obs': 'Consumo eléctrico compresores y lavadora'},
        '4.2.3.04': {'real': Decimal('9000'), 'presup': Decimal('10000'), 'obs': 'Calibración tapadora y etiquetadora lineal'},
        '4.2.3.05': {'real': Decimal('12000'), 'presup': Decimal('12000'), 'obs': 'Amortización monobloc fraccionado'},
        # 4.2.4 Costos Ventas
        '4.2.4.01': {'real': Decimal('15000'), 'presup': Decimal('14000'), 'obs': 'Bines y cajas cosecha granel'},
        '4.2.4.02': {'real': Decimal('25000'), 'presup': Decimal('28000'), 'obs': 'Flexitanks 24.000L para despacho a granel'},
        '4.2.4.03': {'real': Decimal('22000'), 'presup': Decimal('20000'), 'obs': 'Cajas cartón corrugado y paletizado exportación'},
        # 4.2.5 Gastos de Administración
        '4.2.5.01': {'real': Decimal('82000'), 'presup': Decimal('80000'), 'obs': 'Sueldos administración, finanzas y gerencia'},
        '4.2.5.02': {'real': Decimal('28000'), 'presup': Decimal('26000'), 'obs': 'Auditoría externa, asesor legal y agrónomo asesor'},
        '4.2.5.03': {'real': Decimal('18000'), 'presup': Decimal('18000'), 'obs': 'Conectividad satelital en finca, luz oficina y software'},
        '4.2.5.04': {'real': Decimal('4500'), 'presup': Decimal('5000'), 'obs': 'Papelería e insumos de oficina'},
        '4.2.5.05': {'real': Decimal('6000'), 'presup': Decimal('6000'), 'obs': 'Amortización mobiliario y equipos IT'},
        # 4.2.6 Gastos de Comercialización
        '4.2.6.01': {'real': Decimal('36000'), 'presup': Decimal('35000'), 'obs': 'Equipo comercial y de comercio exterior'},
        '4.2.6.02': {'real': Decimal('22000'), 'presup': Decimal('25000'), 'obs': 'Participación feria de alimentos y catálogo web'},
        '4.2.6.03': {'real': Decimal('32000'), 'presup': Decimal('30000'), 'obs': 'Broker exportación San Pablo y Miami'},
        '4.2.6.04': {'real': Decimal('46000'), 'presup': Decimal('44000'), 'obs': 'Flete terrestre puerto Buenos Aires y despacho aduana'},
        '4.2.6.05': {'real': Decimal('14000'), 'presup': Decimal('15000'), 'obs': 'Certificación Kosher, HACCP y Orgánico USDA'},
        # 4.2.7 Resultados Financieros
        '4.2.7.01': {'real': Decimal('26000'), 'presup': Decimal('28000'), 'obs': 'Intereses prefinanciación exportación banco BICE'},
        '4.2.7.02': {'real': Decimal('-8000'), 'presup': Decimal('0'), 'obs': 'Diferencia de cambio neta favorable por divisas liquidación'},
        # 4.2.8 Impuestos
        '4.2.8.01': {'real': Decimal('88000'), 'presup': Decimal('80000'), 'obs': 'Provisión Impuesto a las Ganancias período'},
        '4.2.8.02': {'real': Decimal('24000'), 'presup': Decimal('22000'), 'obs': 'Ingresos Brutos agroindustrial convenio multilateral'},
        '4.2.8.03': {'real': Decimal('6000'), 'presup': Decimal('6000'), 'obs': 'Tasa alumbrado, barrido y canon de riego provincial'},
        '4.2.8.04': {'real': Decimal('9000'), 'presup': Decimal('9000'), 'obs': 'Impuesto a los débitos y créditos bancarios'},
    }

    for c in cuentas_r:
        seccion = determinar_seccion_cuenta(c)
        prefix = '.'.join(c.codigo.split('.')[:4])
        demo = valores_demo.get(prefix, {'real': Decimal('0.00'), 'presup': Decimal('0.00'), 'obs': ''})
        
        monto_real = demo['real'] if inicializar_con_valores_demo else Decimal('0.00')
        monto_presup = demo['presup'] if inicializar_con_valores_demo else Decimal('0.00')
        obs = demo['obs'] if inicializar_con_valores_demo else ''

        LineaCuadroResultado.objects.get_or_create(
            cuadro=cuadro,
            cuenta_contable=c,
            defaults={
                'seccion': seccion,
                'monto_real': monto_real,
                'monto_presupuestado': monto_presup,
                'observaciones': obs
            }
        )

    cuadro.recalcular_totales(save=True)
    return cuadro


def get_or_create_cuadro_default(empresa):
    """Obtiene el cuadro más reciente o crea el informe oficial de la Campaña 2026."""
    from .models import CuadroResultado
    cuadro = CuadroResultado.objects.filter(empresa=empresa).order_by('-fecha_fin', '-created_at').first()
    if cuadro:
        return cuadro

    # Creamos el cuadro insignia de la empresa
    import datetime
    cuadro = CuadroResultado.objects.create(
        empresa=empresa,
        titulo="Campaña Olivícola 2025/2026 - Presentación Directorio",
        tipo_periodo=CuadroResultado.TipoPeriodo.CAMPANA_ANUAL,
        fecha_inicio=datetime.date(2025, 7, 1),
        fecha_fin=datetime.date(2026, 6, 30),
        moneda=CuadroResultado.Moneda.ARS,
        tipo_cambio=Decimal('1050.00'),
        volumen_aceituna_kg=Decimal('1250000.00'),
        volumen_aceite_litros=Decimal('225000.00'),
        estado=CuadroResultado.EstadoCuadro.APROBADO_DIRECTORIO,
        notas_gerencia=(
            "Informe consolidado de Estado de Resultados de la Campaña Olivícola 2025/2026 para presentación a Gerencia General y Directorio.\n\n"
            "Aspectos Clave del Ejercicio:\n"
            "• Rendimiento graso industrial promedio del 18.00% con excelente balance de acidez libre (< 0.28% virgen extra).\n"
            "• Fuerte penetración en mercados internacionales (exportación fraccionada + a granel representa más del 50% de las ventas).\n"
            "• Control riguroso de costos de poda y cosecha mecanizada que permitió mantener un Margen Bruto del 48.5%.\n"
            "• Se cumplió el objetivo de EBITDA superando el 35% de la facturación operativa neta."
        )
    )
    poblar_lineas_cuadro(cuadro, inicializar_con_valores_demo=True)
    # Escalar a ARS para consistencia total en Pesos Argentinos
    for l in cuadro.lineas.all():
        l.monto_real = round(l.monto_real * Decimal('1050.00'), 2)
        l.monto_presupuestado = round(l.monto_presupuestado * Decimal('1050.00'), 2)
        l.save(update_fields=['monto_real', 'monto_presupuestado'])
    cuadro.recalcular_totales(save=True)
    return cuadro
