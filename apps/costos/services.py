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


def calcular_campana_desde_fecha(fecha) -> str:
    """Calcula la campana agricola (jul N-1 -> jun N) a partir de una fecha."""
    if isinstance(fecha, str):
        try:
            fecha_obj = datetime.datetime.strptime(fecha, '%Y-%m-%d').date()
        except ValueError:
            return ""
    else:
        fecha_obj = fecha
    
    if getattr(fecha_obj, 'month', 1) >= 7:
        return f"{getattr(fecha_obj, 'year', 2000)}/{getattr(fecha_obj, 'year', 2000) + 1}"
    else:
        return f"{getattr(fecha_obj, 'year', 2000) - 1}/{getattr(fecha_obj, 'year', 2000)}"


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


def obtener_analitica_rendimiento(finca_id=None, cuadro_id=None, campanas=None) -> dict:
    """
    Agrega datos de rendimiento, costos y rentabilidad estimada por cuadro y campaña.

    Retorna un dict con:
    - analitica_por_cuadro: lista de dicts por cuadro con datos históricos por campaña
    - campanas_disponibles: lista ordenada de campañas detectadas
    - ranking_rendimiento: cuadros ordenados por rinde_kg_ha DESC (mejor campaña)
    - ranking_rentabilidad: cuadros ordenados por margen_por_ha DESC (mejor campaña)
    - evolucion_historica: estructura lista para Chart.js (labels + datasets por cuadro)
    """
    from apps.campos.models import LoteDeCosecha

    # ── Base querysets filtrados ──────────────────────────────────────────────
    lotes_qs = LoteDeCosecha.objects.select_related('cuadro', 'cuadro__finca')
    costos_qs = CostoPorCentro.objects.filter(prorrateo_realizado=False, cuadro__isnull=False)

    if finca_id:
        lotes_qs = lotes_qs.filter(cuadro__finca_id=finca_id)
        costos_qs = costos_qs.filter(finca_id=finca_id)
    if cuadro_id:
        lotes_qs = lotes_qs.filter(cuadro_id=cuadro_id)
        costos_qs = costos_qs.filter(cuadro_id=cuadro_id)

    # ── Campañas disponibles ──────────────────────────────────────────────────
    campanas_set = set(lotes_qs.values_list('campana', flat=True).distinct())
    if campanas:
        campanas_set = campanas_set.intersection(set(campanas))
    campanas_disponibles = sorted(campanas_set)

    # ── Bulk queries para cosecha y costos por cuadro+campaña ────────────────
    # Cosecha: suma de kg por cuadro + campaña, y precio promedio ponderado
    cosecha_raw = lotes_qs.values('cuadro_id', 'campana').annotate(
        total_kg=Sum('kg_cosechados')
    )
    # Para precio promedio ponderado, traemos todos los lotes con precio
    lotes_con_precio = list(
        lotes_qs.filter(precio_venta_estimado_por_kg__isnull=False)
        .values('cuadro_id', 'campana', 'kg_cosechados', 'precio_venta_estimado_por_kg')
    )

    costos_por_cuadro_campana = {}
    for r in CostoPorCentro.objects.filter(
        prorrateo_realizado=False, cuadro__isnull=False, campana__in=campanas_disponibles
    ).values('cuadro_id', 'campana').annotate(total_ars=Sum('importe_ars')):
        costos_por_cuadro_campana[(r['cuadro_id'], r['campana'])] = r['total_ars'] or Decimal('0.00')

    costos_sin_campana_count = CostoPorCentro.objects.filter(
        prorrateo_realizado=False, cuadro__isnull=False, campana=''
    ).count()

    # Map: (cuadro_id, campana) -> total_kg
    cosecha_map = {(r['cuadro_id'], r['campana']): r['total_kg'] or Decimal('0.00') for r in cosecha_raw}

    # Map: (cuadro_id, campana) -> precio_ponderado
    precio_map = {}
    for lote in lotes_con_precio:
        key = (lote['cuadro_id'], lote['campana'])
        if key not in precio_map:
            precio_map[key] = {'kg_sum': Decimal('0'), 'ingreso_sum': Decimal('0')}
        kg = lote['kg_cosechados'] or Decimal('0')
        precio = lote['precio_venta_estimado_por_kg'] or Decimal('0')
        precio_map[key]['kg_sum'] += kg
        precio_map[key]['ingreso_sum'] += kg * precio

    # ── Cuadros involucrados ──────────────────────────────────────────────────
    cuadro_ids = set(cid for (cid, _) in cosecha_map.keys())
    from apps.campos.models import Cuadro as CuadroModel
    cuadros = {c.id: c for c in CuadroModel.objects.select_related('finca').filter(id__in=cuadro_ids, activo=True)}

    if not cuadros and not campanas_disponibles:
        return {
            'analitica_por_cuadro': [],
            'campanas_disponibles': [],
            'ranking_rendimiento': [],
            'ranking_rentabilidad': [],
            'evolucion_historica': {'labels': [], 'datasets': []},
        }

    # ── Construir analítica por cuadro ────────────────────────────────────────
    analitica_por_cuadro = []
    for cuadro_id_key, cuadro in cuadros.items():
        ha = cuadro.hectareas_netas or Decimal('0.00')

        campanas_data = []
        mejor_rinde = Decimal('0.00')
        mejor_margen_ha = None
        prev_rinde = None

        for i, campana in enumerate(campanas_disponibles):
            key = (cuadro_id_key, campana)
            kg = cosecha_map.get(key, Decimal('0.00'))
            rinde_kg_ha = round(kg / ha, 2) if ha > 0 and kg > 0 else Decimal('0.00')

            costo_campana = costos_por_cuadro_campana.get(key, Decimal('0.00'))

            costo_ha = round(costo_campana / ha, 2) if ha > 0 and costo_campana > 0 else Decimal('0.00')
            costo_kg = round(costo_campana / kg, 2) if kg > 0 and costo_campana > 0 else None
            # Ingreso estimado
            pm = precio_map.get(key)
            if pm and pm['kg_sum'] > 0:
                precio_ponderado = round(pm['ingreso_sum'] / pm['kg_sum'], 2)
                ingreso_total = round(kg * precio_ponderado, 2)
            else:
                precio_ponderado = None
                ingreso_total = None

            margen_total = round(ingreso_total - costo_campana, 2) if ingreso_total is not None else None
            margen_ha = round(margen_total / ha, 2) if margen_total is not None and ha > 0 else None

            # Variación vs campaña anterior
            variacion_rinde_pct = None
            if prev_rinde is not None and prev_rinde > 0 and rinde_kg_ha > 0:
                variacion_rinde_pct = round((rinde_kg_ha - prev_rinde) / prev_rinde * 100, 1)
            prev_rinde = rinde_kg_ha if rinde_kg_ha > 0 else prev_rinde

            if rinde_kg_ha > mejor_rinde:
                mejor_rinde = rinde_kg_ha
            if margen_ha is not None and (mejor_margen_ha is None or margen_ha > mejor_margen_ha):
                mejor_margen_ha = margen_ha

            campanas_data.append({
                'campana': campana,
                'kg_cosechados': kg,
                'rinde_kg_ha': rinde_kg_ha,
                'costo_ha': costo_ha,
                'costo_kg': costo_kg,
                'precio_venta_kg': precio_ponderado,
                'ingreso_estimado': ingreso_total,
                'margen_total': margen_total,
                'margen_ha': margen_ha,
                'variacion_rinde_pct': variacion_rinde_pct,
            })

        analitica_por_cuadro.append({
            'cuadro': cuadro,
            'finca': cuadro.finca,
            'hectareas': ha,
            'variedad': cuadro.get_variedad_olivo_display(),
            'mejor_rinde_kg_ha': mejor_rinde,
            'mejor_margen_ha': mejor_margen_ha,
            'campanas': campanas_data,
        })

    # ── Rankings ──────────────────────────────────────────────────────────────
    ranking_rendimiento = sorted(
        analitica_por_cuadro,
        key=lambda x: x['mejor_rinde_kg_ha'],
        reverse=True
    )
    ranking_rentabilidad = sorted(
        [it for it in analitica_por_cuadro if it['mejor_margen_ha'] is not None],
        key=lambda x: x['mejor_margen_ha'],
        reverse=True
    )

    # ── Evolución histórica para Chart.js ────────────────────────────────────
    COLORS = ['#3D4A2A', '#8FA872', '#A2B38F', '#4E5F36', '#D5DFC9', '#6B7F52']
    datasets = []
    for idx, it in enumerate(analitica_por_cuadro):
        color = COLORS[idx % len(COLORS)]
        data_points = [
            float(c['rinde_kg_ha']) if c['rinde_kg_ha'] else None
            for c in it['campanas']
        ]
        datasets.append({
            'label': f"{it['cuadro'].codigo} ({it['variedad'][:8]})",
            'data': data_points,
            'borderColor': color,
            'backgroundColor': color + '22',
            'tension': 0.3,
            'fill': False,
            'pointRadius': 5,
            'pointHoverRadius': 7,
        })

    evolucion_historica = {
        'labels': campanas_disponibles,
        'datasets': datasets,
    }

    return {
        'analitica_por_cuadro': analitica_por_cuadro,
        'campanas_disponibles': campanas_disponibles,
        'ranking_rendimiento': ranking_rendimiento,
        'ranking_rentabilidad': ranking_rentabilidad,
        'evolucion_historica': evolucion_historica,
    }

