import datetime
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import CostoPorCentro
from apps.campos.models import Cuadro
from apps.core.models import CentroDeCosto, Finca
from apps.finanzas.models import (
    CuentaContable, 
    CuentaCorriente, 
    Cuenta, 
    MovimientoFinanciero, 
    TipoCambioMensual,
    CuadroResultado,
    LineaCuadroResultado,
)
from apps.finanzas.services import registrar_movimiento_financiero, determinar_seccion_cuenta


def resolver_cuenta_contable_defecto(tipo_origen: str, centro_de_costo: CentroDeCosto = None) -> CuentaContable:
    """Busca o infiere la cuenta contable imputable apropiada para el costo."""
    if centro_de_costo and centro_de_costo.cuenta_contable_defecto:
        return centro_de_costo.cuenta_contable_defecto

    mapping = {
        CostoPorCentro.TipoOrigen.MANO_DE_OBRA: '4.2.1.01.000000',
        CostoPorCentro.TipoOrigen.INSUMO: '4.2.1.02.000000',
        CostoPorCentro.TipoOrigen.COMBUSTIBLE_MAQUINARIA: '4.2.1.06.000000',
        CostoPorCentro.TipoOrigen.SERVICIO_CONTRATISTA: '4.2.1.05.000000',
        CostoPorCentro.TipoOrigen.ENERGIA_RIEGO: '4.2.1.02.000000',
        CostoPorCentro.TipoOrigen.MANTENIMIENTO: '4.2.1.07.000000',
        CostoPorCentro.TipoOrigen.ESTRUCTURA_ADMIN: '4.2.5.01.000000',
    }

    codigo = mapping.get(tipo_origen, '4.2.1.02.000000')
    cta = CuentaContable.objects.filter(codigo=codigo, es_imputable=True).first()
    if not cta:
        cta = CuentaContable.objects.filter(codigo__startswith='4.2.', es_imputable=True).first()
    return cta


@transaction.atomic
def registrar_costo(
    centro_de_costo: CentroDeCosto,
    finca: Finca,
    fecha: datetime.date,
    importe_ars: Decimal,
    tipo_origen: str,
    descripcion: str,
    cuadro: Cuadro = None,
    cuenta_contable: CuentaContable = None,
    proveedor: CuentaCorriente = None,
    metodo_pago: str = 'SOLO_COSTO',
    cuenta_financiera: Cuenta = None,
    documento_origen_tipo: str = '',
    documento_origen_id: int = None,
    usuario = None
) -> CostoPorCentro:
    """
    Registra una imputación de costo por centro y lote agrícola,
    integrando el Plan de Cuentas, Proveedores y Movimiento Financiero.
    """
    if importe_ars <= Decimal('0'):
        raise ValueError("El importe del costo debe ser mayor a cero.")

    # 1. Resolver cuenta contable si no vino explícita
    if not cuenta_contable:
        cuenta_contable = resolver_cuenta_contable_defecto(tipo_origen, centro_de_costo)

    # 2. Calcular importe en USD según Tipo de Cambio del mes
    tc = TipoCambioMensual.get_tc(ano=fecha.year, mes=fecha.month)
    importe_usd = round(importe_ars / tc, 2) if tc > 0 else Decimal('0.00')

    movimiento_fin = None

    # 3. Impacto en Proveedor (si es a Cuenta Corriente)
    if metodo_pago == 'CUENTA_CORRIENTE' and proveedor:
        # Aumenta nuestra deuda con el proveedor (saldo más negativo)
        proveedor.saldo_actual -= importe_ars
        proveedor.save(update_fields=['saldo_actual', 'updated_at'])

    # 4. Impacto en Caja/Banco (si es Contado)
    elif metodo_pago == 'CONTADO' and cuenta_financiera:
        concepto_pago = f"Pago Costo ({descripcion[:80]} - {finca.nombre})"
        movimiento_fin = registrar_movimiento_financiero(
            cuenta=cuenta_financiera,
            tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
            importe=importe_ars,
            concepto=concepto_pago,
            comprobante_tipo=documento_origen_tipo or 'Comprobante Costo',
            comprobante_nro=str(documento_origen_id or ''),
            cuenta_corriente=proveedor,
            centro_de_costo=centro_de_costo,
            finca=finca,
            usuario=usuario,
            fecha=fecha
        )

    # 5. Crear el registro en CostoPorCentro
    costo = CostoPorCentro.objects.create(
        centro_de_costo=centro_de_costo,
        finca=finca,
        cuadro=cuadro,
        fecha=fecha,
        importe_ars=importe_ars,
        importe_usd=importe_usd,
        tipo_origen=tipo_origen,
        descripcion=descripcion,
        cuenta_contable=cuenta_contable,
        proveedor=proveedor,
        movimiento_financiero=movimiento_fin,
        documento_origen_tipo=documento_origen_tipo,
        documento_origen_id=documento_origen_id
    )

    # 6. Sincronizar automáticamente con el Cuadro de Resultados (P&L) activo
    try:
        sincronizar_costos_con_cuadro_resultado()
    except Exception:
        pass

    return costo


@transaction.atomic
def prorratear_costo_indirecto(costo: CostoPorCentro, usuario=None) -> int:
    """
    Distribuye un costo indirecto de finca (sin cuadro asignado) entre todos los
    cuadros productivos de dicha finca según su superficie neta en hectáreas.
    Marca el costo original con prorrateo_realizado=True para no duplicar sumas.
    """
    if costo.cuadro is not None:
        raise ValueError("Solo los costos indirectos generales (sin cuadro asignado) pueden ser prorrateados.")

    if costo.prorrateo_realizado:
        raise ValueError("Este costo indirecto ya ha sido prorrateado previamente.")

    cuadros = Cuadro.objects.filter(finca=costo.finca, activo=True, hectareas_netas__gt=0).order_by('codigo')
    if not cuadros.exists():
        raise ValueError(f"La finca {costo.finca.nombre} no tiene cuadros activos con hectáreas registradas.")

    total_ha = sum(cua.hectareas_netas for cua in cuadros)
    if total_ha <= Decimal('0'):
        raise ValueError("El total de hectáreas de los cuadros de la finca es cero.")

    acum_ars = Decimal('0')
    acum_usd = Decimal('0')
    items_generados = []
    lista_cuadros = list(cuadros)

    for i, cua in enumerate(lista_cuadros):
        is_last = (i == len(lista_cuadros) - 1)
        ha = cua.hectareas_netas
        
        if is_last:
            # Asignar residuo de redondeo al último cuadro
            sub_ars = costo.importe_ars - acum_ars
            sub_usd = costo.importe_usd - acum_usd
        else:
            pct = ha / total_ha
            sub_ars = round(costo.importe_ars * pct, 2)
            sub_usd = round(costo.importe_usd * pct, 2)
            acum_ars += sub_ars
            acum_usd += sub_usd

        item = CostoPorCentro(
            centro_de_costo=costo.centro_de_costo,
            finca=costo.finca,
            cuadro=cua,
            fecha=costo.fecha,
            importe_ars=sub_ars,
            importe_usd=sub_usd,
            tipo_origen=costo.tipo_origen,
            descripcion=f"[Prorrateo {ha} ha ({cua.codigo})] {costo.descripcion}",
            cuenta_contable=costo.cuenta_contable,
            proveedor=costo.proveedor,
            movimiento_financiero=costo.movimiento_financiero,
            es_prorrateado=True,
            costo_origen_prorrateo=costo,
            documento_origen_tipo='Prorrateo',
            documento_origen_id=costo.id
        )
        items_generados.append(item)

    CostoPorCentro.objects.bulk_create(items_generados)

    # Marcar costo padre como prorrateado
    costo.prorrateo_realizado = True
    costo.save(update_fields=['prorrateo_realizado', 'updated_at'])

    try:
        sincronizar_costos_con_cuadro_resultado()
    except Exception:
        pass

    return len(items_generados)


@transaction.atomic
def sincronizar_costos_con_cuadro_resultado(cuadro_resultado: CuadroResultado = None) -> dict:
    """
    Sincroniza las imputaciones reales de CostoPorCentro con las líneas contables
    del Estado de Resultados (P&L), asegurando coherencia total entre gestión y contabilidad.
    """
    if not cuadro_resultado:
        cuadro_resultado = CuadroResultado.objects.order_by('-fecha_fin', '-id').first()
        if not cuadro_resultado:
            raise ValueError("No se encontró ningún Cuadro de Resultados activo para sincronizar.")

    desde = cuadro_resultado.fecha_inicio
    hasta = cuadro_resultado.fecha_fin

    # Tomar costos dentro del período, excluyendo los padres ya distribuidos para no duplicar sumas
    costos_periodo = CostoPorCentro.objects.filter(
        fecha__gte=desde,
        fecha__lte=hasta,
        prorrateo_realizado=False
    ).select_related('cuenta_contable', 'centro_de_costo')

    # Agrupar sumas por cuenta contable efectiva
    totales_por_cuenta = {}
    for c in costos_periodo:
        cta = c.cuenta_contable or resolver_cuenta_contable_defecto(c.tipo_origen, c.centro_de_costo)
        if not cta:
            continue
        totales_por_cuenta[cta.id] = totales_por_cuenta.get(cta.id, Decimal('0.00')) + c.importe_ars

    cuentas_actualizadas = 0
    total_sincronizado = Decimal('0.00')

    for cta_id, total_ars in totales_por_cuenta.items():
        cta = CuentaContable.objects.get(id=cta_id)
        linea, _ = LineaCuadroResultado.objects.get_or_create(
            cuadro=cuadro_resultado,
            cuenta_contable=cta,
            defaults={
                'seccion': determinar_seccion_cuenta(cta),
                'monto_real': Decimal('0.00'),
                'monto_presupuestado': Decimal('0.00')
            }
        )
        linea.monto_real = total_ars
        linea.save(update_fields=['monto_real', 'updated_at'])
        cuentas_actualizadas += 1
        total_sincronizado += total_ars

    # Recalcular subtotales en cascada del cuadro
    cuadro_resultado.recalcular_totales(save=True)

    return {
        'cuadro': cuadro_resultado,
        'cuentas_actualizadas': cuentas_actualizadas,
        'total_sincronizado_ars': total_sincronizado,
        'nuevo_costo_produccion': cuadro_resultado.costo_produccion,
        'nuevo_ebitda': cuadro_resultado.ebitda,
        'nuevo_resultado_neto': cuadro_resultado.resultado_neto,
    }
