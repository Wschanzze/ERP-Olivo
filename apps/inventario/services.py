"""
Capa de servicios transaccionales para el módulo Inventario.
Confirma recepciones de mercadería de forma atómica:
- Genera MovimientoStock por cada ítem recibido
- Actualiza StockPorDeposito y recalcula PPP del Insumo
- Opcionalmente registra la deuda en la CuentaCorriente del proveedor
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone


def confirmar_recepcion(recepcion_id: int, usuario=None) -> dict:
    """
    Confirma una RecepcionMercaderia de forma atómica.

    Flujo:
    1. Bloquea la recepción con select_for_update
    2. Por cada ItemRecepcion:
       a. Crea un MovimientoStock ENTRADA_COMPRA
       b. Actualiza StockPorDeposito (crea si no existe)
       c. Recalcula PPP del Insumo
    3. Actualiza el estado de la RecepcionMercaderia a CONFIRMADA
    4. Si corresponde (registrar_deuda_al_confirmar OR OC.registrar_deuda_al_aprobar),
       actualiza la CuentaCorriente del proveedor.
    5. Marca la OC como RECIBIDA o RECIBIDA_PARCIAL según el caso.

    Retorna: dict con 'ok', 'mensaje', 'movimientos_creados'
    """
    from .models import RecepcionMercaderia, MovimientoStock, StockPorDeposito, ItemRecepcion
    from apps.finanzas.models import CuentaCorriente

    with transaction.atomic():
        try:
            recepcion = RecepcionMercaderia.objects.select_for_update().get(pk=recepcion_id)
        except RecepcionMercaderia.DoesNotExist:
            return {'ok': False, 'mensaje': 'Recepción no encontrada.', 'movimientos_creados': 0}

        if recepcion.estado == RecepcionMercaderia.Estado.CONFIRMADA:
            return {'ok': False, 'mensaje': 'La recepción ya fue confirmada.', 'movimientos_creados': 0}

        if recepcion.estado == RecepcionMercaderia.Estado.ANULADA:
            return {'ok': False, 'mensaje': 'No se puede confirmar una recepción anulada.', 'movimientos_creados': 0}

        items = recepcion.items.select_related('insumo').all()
        movimientos_creados = 0
        total_real = Decimal('0.00')

        for item in items:
            insumo = item.insumo
            cantidad = item.cantidad_recibida
            precio_nuevo = item.precio_unitario_real_ars

            if cantidad <= 0:
                continue

            # ── 1. Crear MovimientoStock ──────────────────────────────────────
            mov = MovimientoStock.objects.create(
                insumo=insumo,
                deposito=recepcion.deposito_destino,
                tipo=MovimientoStock.TipoMovimiento.ENTRADA_COMPRA,
                cantidad=cantidad,
                costo_unitario=precio_nuevo,
                fecha=timezone.now(),
                motivo=f"Recepción OC {recepcion.orden.numero} — {recepcion.numero_remito_proveedor or 'S/R'}",
                referencia_origen=f"OC-{recepcion.orden.numero}",
                usuario=usuario,
            )
            item.movimiento_stock = mov
            item.save(update_fields=['movimiento_stock'])
            movimientos_creados += 1

            # ── 2. Actualizar StockPorDeposito ────────────────────────────────
            stock_dep, _ = StockPorDeposito.objects.get_or_create(
                deposito=recepcion.deposito_destino,
                insumo=insumo,
                defaults={'cantidad': Decimal('0.00')}
            )
            stock_dep.cantidad += cantidad
            stock_dep.save(update_fields=['cantidad'])

            # ── 3. Recalcular PPP (Precio Promedio Ponderado) ─────────────────
            stock_previo = insumo.stock_actual  # antes de la entrada
            costo_previo = insumo.costo_unitario_ars

            stock_nuevo = stock_previo + cantidad
            if stock_nuevo > 0:
                ppp_nuevo = ((stock_previo * costo_previo) + (cantidad * precio_nuevo)) / stock_nuevo
            else:
                ppp_nuevo = precio_nuevo

            insumo.stock_actual = stock_nuevo
            insumo.costo_unitario_ars = round(ppp_nuevo, 2)
            insumo.save(update_fields=['stock_actual', 'costo_unitario_ars', 'updated_at'])

            total_real += item.subtotal_real_ars

        # ── 4. Actualizar total y estado de la recepción ──────────────────────
        recepcion.total_real_ars = total_real
        recepcion.estado = RecepcionMercaderia.Estado.CONFIRMADA
        recepcion.save(update_fields=['total_real_ars', 'estado', 'updated_at'])

        # ── 5. Registrar deuda en CuentaCorriente del proveedor ───────────────
        oc = recepcion.orden
        debe_registrar_deuda = (
            recepcion.registrar_deuda_al_confirmar or oc.registrar_deuda_al_aprobar
        )

        if debe_registrar_deuda and total_real > 0:
            proveedor_cc = oc.proveedor
            # Para proveedor: saldo negativo = debemos pagarle
            proveedor_cc.saldo_actual -= total_real
            proveedor_cc.save(update_fields=['saldo_actual', 'updated_at'])

        # ── 6. Actualizar estado de la OC ─────────────────────────────────────
        todas_recepciones = oc.recepciones.filter(estado=RecepcionMercaderia.Estado.CONFIRMADA).count()
        total_recepciones = oc.recepciones.count()
        if todas_recepciones == total_recepciones:
            oc.estado = 'RECIBIDA'
        else:
            oc.estado = 'RECIBIDA_PARCIAL'
        oc.save(update_fields=['estado', 'updated_at'])

        return {
            'ok': True,
            'mensaje': f'Recepción confirmada. {movimientos_creados} movimiento(s) de stock generados.',
            'movimientos_creados': movimientos_creados,
        }


def realizar_transferencia_stock(
    insumo_id: int,
    deposito_origen_id: int,
    deposito_destino_id: int,
    cantidad: Decimal,
    motivo: str = "",
    usuario=None
) -> dict:
    """
    Ejecuta una transferencia atómica de existencias entre dos depósitos físicos.
    - Valida que el depósito origen tenga stock suficiente.
    - Descuenta del depósito origen y suma al depósito destino.
    - El stock global del insumo se mantiene intacto.
    - Genera un MovimientoStock de tipo TRANSFERENCIA con trazabilidad completa.
    """
    from django.core.exceptions import ValidationError
    from .models import Insumo, Deposito, StockPorDeposito, MovimientoStock

    cantidad = Decimal(str(cantidad))
    if cantidad <= Decimal('0.00'):
        raise ValidationError("La cantidad a transferir debe ser mayor a cero.")

    if deposito_origen_id == deposito_destino_id:
        raise ValidationError("El depósito de origen y de destino no pueden ser el mismo.")

    with transaction.atomic():
        insumo = Insumo.objects.select_for_update().get(pk=insumo_id)
        deposito_origen = Deposito.objects.get(pk=deposito_origen_id)
        deposito_destino = Deposito.objects.get(pk=deposito_destino_id)

        stock_origen, _ = StockPorDeposito.objects.select_for_update().get_or_create(
            deposito=deposito_origen,
            insumo=insumo,
            defaults={'cantidad': Decimal('0.00')}
        )

        if stock_origen.cantidad < cantidad:
            raise ValidationError(
                f"Stock insuficiente en '{deposito_origen.nombre}'. "
                f"Disponible: {stock_origen.cantidad} {insumo.get_unidad_medida_display()}, "
                f"solicitado: {cantidad}."
            )

        stock_destino, _ = StockPorDeposito.objects.select_for_update().get_or_create(
            deposito=deposito_destino,
            insumo=insumo,
            defaults={'cantidad': Decimal('0.00')}
        )

        # Actualizar existencias locales
        stock_origen.cantidad -= cantidad
        stock_origen.save(update_fields=['cantidad', 'updated_at'])

        stock_destino.cantidad += cantidad
        stock_destino.save(update_fields=['cantidad', 'updated_at'])

        # Comprobante de referencia
        now = timezone.now()
        ref_codigo = f"TRF-{now.strftime('%y%m%d%H%M')}"
        motivo_texto = motivo.strip() or f"Traslado de {deposito_origen.nombre} a {deposito_destino.nombre}"

        # Registrar movimiento de auditoría
        mov = MovimientoStock.objects.create(
            insumo=insumo,
            deposito=deposito_origen,
            deposito_destino=deposito_destino,
            tipo=MovimientoStock.TipoMovimiento.TRANSFERENCIA,
            cantidad=cantidad,
            costo_unitario=insumo.costo_unitario_ars,
            fecha=now,
            motivo=motivo_texto,
            referencia_origen=ref_codigo,
            usuario=usuario
        )

        return {
            'ok': True,
            'mensaje': f"Transferencia de {cantidad} {insumo.get_unidad_medida_display()} realizada exitosamente.",
            'movimiento': mov,
            'stock_origen_restante': stock_origen.cantidad,
            'stock_destino_total': stock_destino.cantidad,
        }


def realizar_ajuste_stock(
    insumo_id: int,
    deposito_id: int,
    tipo_ajuste: str,
    cantidad: Decimal,
    costo_unitario: Decimal = None,
    motivo: str = "",
    usuario=None
) -> dict:
    """
    Registra un ajuste manual de inventario (positivo, negativo o merma/vencimiento).
    - Actualiza tanto la existencia del depósito como el stock_actual global del insumo.
    - Si es AJUSTE_POSITIVO y se indica costo_unitario, recalcula el PPP del insumo.
    - Valida que no queden existencias negativas en salidas o mermas.
    - Genera el MovimientoStock correspondiente.
    """
    from django.core.exceptions import ValidationError
    from .models import Insumo, Deposito, StockPorDeposito, MovimientoStock

    tipos_validos = [
        MovimientoStock.TipoMovimiento.AJUSTE_POSITIVO,
        MovimientoStock.TipoMovimiento.AJUSTE_NEGATIVO,
        MovimientoStock.TipoMovimiento.SALIDA_MERMA
    ]
    if tipo_ajuste not in tipos_validos:
        raise ValidationError(f"Tipo de ajuste '{tipo_ajuste}' no es válido.")

    cantidad = Decimal(str(cantidad))
    if cantidad <= Decimal('0.00'):
        raise ValidationError("La cantidad a ajustar debe ser mayor a cero.")

    with transaction.atomic():
        insumo = Insumo.objects.select_for_update().get(pk=insumo_id)
        deposito = Deposito.objects.get(pk=deposito_id)

        stock_dep, _ = StockPorDeposito.objects.select_for_update().get_or_create(
            deposito=deposito,
            insumo=insumo,
            defaults={'cantidad': Decimal('0.00')}
        )

        # Determinar costo unitario imputado
        if costo_unitario is not None and Decimal(str(costo_unitario)) > Decimal('0.00'):
            costo_aplicado = Decimal(str(costo_unitario))
        else:
            costo_aplicado = insumo.costo_unitario_ars

        now = timezone.now()
        prefix = "MER" if tipo_ajuste == MovimientoStock.TipoMovimiento.SALIDA_MERMA else "AJU"
        ref_codigo = f"{prefix}-{now.strftime('%y%m%d%H%M')}"

        if tipo_ajuste == MovimientoStock.TipoMovimiento.AJUSTE_POSITIVO:
            # Incrementar depósito
            stock_dep.cantidad += cantidad
            stock_dep.save(update_fields=['cantidad', 'updated_at'])

            # Recalcular PPP si vino costo informado
            stock_previo = insumo.stock_actual
            costo_previo = insumo.costo_unitario_ars
            stock_nuevo = stock_previo + cantidad

            if costo_unitario is not None and Decimal(str(costo_unitario)) > 0 and stock_nuevo > 0:
                ppp_nuevo = ((stock_previo * costo_previo) + (cantidad * costo_aplicado)) / stock_nuevo
                insumo.costo_unitario_ars = round(ppp_nuevo, 2)

            insumo.stock_actual = stock_nuevo
            insumo.save(update_fields=['stock_actual', 'costo_unitario_ars', 'updated_at'])

        else:
            # AJUSTE_NEGATIVO o SALIDA_MERMA
            if stock_dep.cantidad < cantidad:
                raise ValidationError(
                    f"Stock insuficiente en '{deposito.nombre}'. "
                    f"Disponible: {stock_dep.cantidad} {insumo.get_unidad_medida_display()}, "
                    f"ajuste solicitado: {cantidad}."
                )

            if insumo.stock_actual < cantidad:
                raise ValidationError(
                    f"Stock global insuficiente. "
                    f"Disponible: {insumo.stock_actual} {insumo.get_unidad_medida_display()}, "
                    f"ajuste solicitado: {cantidad}."
                )

            stock_dep.cantidad -= cantidad
            stock_dep.save(update_fields=['cantidad', 'updated_at'])

            insumo.stock_actual -= cantidad
            insumo.save(update_fields=['stock_actual', 'updated_at'])

        motivo_texto = motivo.strip() or f"{tipo_ajuste.replace('_', ' ').title()} en {deposito.nombre}"

        mov = MovimientoStock.objects.create(
            insumo=insumo,
            deposito=deposito,
            tipo=tipo_ajuste,
            cantidad=cantidad,
            costo_unitario=costo_aplicado,
            fecha=now,
            motivo=motivo_texto,
            referencia_origen=ref_codigo,
            usuario=usuario
        )

        return {
            'ok': True,
            'mensaje': f"Ajuste ({tipo_ajuste}) de {cantidad} {insumo.get_unidad_medida_display()} registrado.",
            'movimiento': mov,
            'stock_deposito_resultante': stock_dep.cantidad,
            'stock_global_resultante': insumo.stock_actual,
        }


def obtener_kardex_insumo(
    insumo_id: int,
    deposito_id: int = None,
    fecha_desde=None,
    fecha_hasta=None
) -> dict:
    """
    Genera el Kardex cronológico Físico y Valorado para un insumo.
    Calcula de forma acumulativa y progresiva:
    - Entradas (+ unidades y valor)
    - Salidas (- unidades y valor)
    - Saldo físico en cada movimiento
    - Saldo valorizado acumulado
    """
    from django.db.models import Q
    from .models import Insumo, Deposito, MovimientoStock

    insumo = Insumo.objects.select_related('categoria').get(pk=insumo_id)

    # Base de movimientos en orden cronológico estricto
    qs = MovimientoStock.objects.filter(insumo=insumo).select_related(
        'deposito', 'deposito_destino', 'usuario'
    ).order_by('fecha', 'id')

    deposito_seleccionado = None
    if deposito_id:
        try:
            deposito_seleccionado = Deposito.objects.get(pk=deposito_id)
            qs = qs.filter(Q(deposito_id=deposito_id) | Q(deposito_destino_id=deposito_id))
        except Deposito.DoesNotExist:
            deposito_id = None

    if fecha_desde:
        qs = qs.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__date__lte=fecha_hasta)

    saldo_cantidad = Decimal('0.00')
    total_entradas_cant = Decimal('0.00')
    total_salidas_cant = Decimal('0.00')
    total_entradas_val = Decimal('0.00')
    total_salidas_val = Decimal('0.00')

    movimientos_decorados = []

    for mov in qs:
        tipo = mov.tipo
        cant = mov.cantidad
        costo_u = mov.costo_unitario or insumo.costo_unitario_ars
        costo_total = round(cant * costo_u, 2)

        cant_in = Decimal('0.00')
        cant_out = Decimal('0.00')
        val_in = Decimal('0.00')
        val_out = Decimal('0.00')
        tipo_etiqueta = mov.get_tipo_display()
        es_transferencia = (tipo == MovimientoStock.TipoMovimiento.TRANSFERENCIA)

        if tipo in (MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, MovimientoStock.TipoMovimiento.AJUSTE_POSITIVO):
            cant_in = cant
            val_in = costo_total
            saldo_cantidad += cant_in
        elif tipo in (MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO, MovimientoStock.TipoMovimiento.SALIDA_MERMA, MovimientoStock.TipoMovimiento.AJUSTE_NEGATIVO):
            cant_out = cant
            val_out = costo_total
            saldo_cantidad -= cant_out
        elif es_transferencia:
            if deposito_id:
                # Si estamos filtrando por un depósito en específico
                if mov.deposito_id == deposito_id:
                    # Salió de este depósito
                    cant_out = cant
                    val_out = costo_total
                    saldo_cantidad -= cant_out
                    tipo_etiqueta = f"Transferencia Enviada (a {mov.deposito_destino.nombre if mov.deposito_destino else 'Otro'})"
                else:
                    # Entró a este depósito
                    cant_in = cant
                    val_in = costo_total
                    saldo_cantidad += cant_in
                    tipo_etiqueta = f"Transferencia Recibida (de {mov.deposito.nombre})"
            else:
                # Visión Global de la empresa: el total no varía
                tipo_etiqueta = f"Transferencia ({mov.deposito.nombre} → {mov.deposito_destino.nombre if mov.deposito_destino else 'Otro'})"
                # Reflejamos el evento sin alterar el total global acumulado
                cant_in = Decimal('0.00')
                cant_out = Decimal('0.00')

        total_entradas_cant += cant_in
        total_salidas_cant += cant_out
        total_entradas_val += val_in
        total_salidas_val += val_out

        saldo_val = round(saldo_cantidad * (insumo.costo_unitario_ars or Decimal('0.00')), 2)

        movimientos_decorados.append({
            'objeto': mov,
            'fecha': mov.fecha,
            'tipo_codigo': tipo,
            'tipo_display': tipo_etiqueta,
            'referencia': mov.referencia_origen or '—',
            'motivo': mov.motivo,
            'deposito_origen': mov.deposito,
            'deposito_destino': mov.deposito_destino,
            'costo_unitario': costo_u,
            'cant_entrada': cant_in if cant_in > 0 else None,
            'cant_salida': cant_out if cant_out > 0 else None,
            'val_entrada': val_in if val_in > 0 else None,
            'val_salida': val_out if val_out > 0 else None,
            'saldo_cantidad': saldo_cantidad,
            'saldo_valor_ars': saldo_val,
            'usuario': mov.usuario,
            'es_transferencia': es_transferencia,
        })

    # Si no hubo movimientos pero el insumo tiene stock actual, asegurar consistencia
    saldo_final_unidades = saldo_cantidad if movimientos_decorados else insumo.stock_actual
    saldo_final_valorizado = round(saldo_final_unidades * insumo.costo_unitario_ars, 2)

    return {
        'insumo': insumo,
        'deposito_filtro': deposito_seleccionado,
        'movimientos': movimientos_decorados,
        'total_movimientos': len(movimientos_decorados),
        'total_entradas_cant': total_entradas_cant,
        'total_salidas_cant': total_salidas_cant,
        'total_entradas_val': total_entradas_val,
        'total_salidas_val': total_salidas_val,
        'saldo_final_unidades': saldo_final_unidades,
        'saldo_final_valorizado': saldo_final_valorizado,
    }


# ──────────────────────────────────────────────────────────────────────────────
# SERVICIOS ANALÍTICOS Y CONTROL DE GESTIÓN (FASE 2)
# ──────────────────────────────────────────────────────────────────────────────

def calcular_clasificacion_abc_inventario() -> dict:
    """
    Calcula la Clasificación ABC (Curva de Pareto) del inventario agrícola.
    Criterio de valorización económica inmovilizada ($ ARS):
    - Clase A: Hasta el 80% del valor total acumulado (artículos de máximo impacto).
    - Clase B: Siguiente 15% (80% al 95% acumulado).
    - Clase C: 5% restante (95% al 100% acumulado, bajo impacto económico individual).
    """
    from .models import Insumo

    insumos = list(
        Insumo.objects.filter(activo=True).select_related(
            'categoria', 'cuenta_contable', 'categoria__cuenta_contable_activo'
        )
    )

    items = []
    total_valor = Decimal('0.00')

    for ins in insumos:
        valor_item = round(Decimal(str(ins.stock_actual)) * Decimal(str(ins.costo_unitario_ars)), 2)
        total_valor += valor_item
        cuenta_activo = ins.cuenta_contable or ins.categoria.cuenta_contable_activo
        items.append({
            'insumo': ins,
            'valor': valor_item,
            'cuenta_activo': cuenta_activo,
            'stock_actual': ins.stock_actual,
            'costo_unitario_ars': ins.costo_unitario_ars,
        })

    # Ordenar descendentemente por valor inmovilizado
    items.sort(key=lambda x: x['valor'], reverse=True)

    acumulado_valor = Decimal('0.00')
    items_clasificados = []

    resumen_a = {'cantidad': 0, 'valor': Decimal('0.00'), 'pct_valor': Decimal('0.00')}
    resumen_b = {'cantidad': 0, 'valor': Decimal('0.00'), 'pct_valor': Decimal('0.00')}
    resumen_c = {'cantidad': 0, 'valor': Decimal('0.00'), 'pct_valor': Decimal('0.00')}

    for idx, it in enumerate(items):
        acumulado_valor += it['valor']
        pct_indiv = round((it['valor'] / total_valor * Decimal('100.0')) if total_valor > 0 else Decimal('0.0'), 2)
        pct_acum = round((acumulado_valor / total_valor * Decimal('100.0')) if total_valor > 0 else Decimal('0.0'), 2)

        if total_valor == 0:
            clase = 'C'
        elif pct_acum <= Decimal('80.00') or (idx == 0 and pct_acum > Decimal('80.00')):
            clase = 'A'
        elif pct_acum <= Decimal('95.00') or (resumen_b['cantidad'] == 0 and clase != 'A'):
            clase = 'B'
        else:
            clase = 'C'

        it['clase'] = clase
        it['pct_individual'] = pct_indiv
        it['pct_acumulado'] = pct_acum
        items_clasificados.append(it)

        if clase == 'A':
            resumen_a['cantidad'] += 1
            resumen_a['valor'] += it['valor']
        elif clase == 'B':
            resumen_b['cantidad'] += 1
            resumen_b['valor'] += it['valor']
        else:
            resumen_c['cantidad'] += 1
            resumen_c['valor'] += it['valor']

    if total_valor > 0:
        resumen_a['pct_valor'] = round(resumen_a['valor'] / total_valor * 100, 1)
        resumen_b['pct_valor'] = round(resumen_b['valor'] / total_valor * 100, 1)
        resumen_c['pct_valor'] = round(resumen_c['valor'] / total_valor * 100, 1)

    return {
        'total_valor': total_valor,
        'total_insumos': len(items_clasificados),
        'items': items_clasificados,
        'resumen_a': resumen_a,
        'resumen_b': resumen_b,
        'resumen_c': resumen_c,
    }


def calcular_matriz_cobertura_y_reorden(dias_analisis: int = 60) -> dict:
    """
    Calcula la tasa de consumo diario de cada insumo en base a los Partes Diarios recientes
    y proyecta los días de cobertura restante antes de llegar al quiebre de stock.
    Determina la cantidad sugerida de compra para punto de reorden.
    """
    from datetime import timedelta
    from django.db.models import Sum
    from .models import Insumo, MovimientoStock

    ahora = timezone.now()
    fecha_desde = ahora - timedelta(days=dias_analisis)

    insumos = Insumo.objects.filter(activo=True).select_related('categoria').order_by('nombre')

    # Suma de salidas de campo por insumo en el período
    salidas_qs = MovimientoStock.objects.filter(
        tipo=MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO,
        fecha__gte=fecha_desde
    ).values('insumo_id').annotate(total_salida=Sum('cantidad'))

    salidas_map = {item['insumo_id']: item['total_salida'] for item in salidas_qs}

    filas = []
    conteo_criticos = 0
    conteo_reorden = 0
    conteo_seguros = 0

    for ins in insumos:
        consumo_total = salidas_map.get(ins.id, Decimal('0.00'))
        consumo_diario = round(consumo_total / Decimal(str(dias_analisis)), 3)

        dias_cobertura = None
        if consumo_diario > Decimal('0.000'):
            dias_cobertura = int(ins.stock_actual / consumo_diario)

        # Criterio de Riesgo
        es_critico = (ins.stock_actual <= ins.stock_minimo) or (dias_cobertura is not None and dias_cobertura <= 15)
        es_reorden = not es_critico and (dias_cobertura is not None and dias_cobertura <= 30)

        if es_critico:
            nivel = 'CRITICO'
            color = 'rose'
            conteo_criticos += 1
        elif es_reorden:
            nivel = 'REORDEN'
            color = 'amber'
            conteo_reorden += 1
        else:
            nivel = 'SEGURO'
            color = 'emerald'
            conteo_seguros += 1

        # Cálculo de cantidad sugerida de compra:
        # Stock objetivo: el mayor entre 2 veces el stock mínimo o 45 días de consumo
        stock_objetivo = max(ins.stock_minimo * Decimal('2.0'), consumo_diario * Decimal('45.0'))
        if ins.stock_actual < stock_objetivo:
            cantidad_sugerida = round(stock_objetivo - ins.stock_actual, 2)
        else:
            cantidad_sugerida = Decimal('0.00')

        filas.append({
            'insumo': ins,
            'stock_actual': ins.stock_actual,
            'stock_minimo': ins.stock_minimo,
            'consumo_periodo': consumo_total,
            'consumo_diario': consumo_diario,
            'dias_cobertura': dias_cobertura,
            'nivel': nivel,
            'color': color,
            'cantidad_sugerida': cantidad_sugerida,
            'costo_estimado_ars': round(cantidad_sugerida * ins.costo_unitario_ars, 2),
        })

    # Ordenar poniendo primero los críticos y luego los de reorden
    filas.sort(key=lambda x: (0 if x['nivel'] == 'CRITICO' else (1 if x['nivel'] == 'REORDEN' else 2), x['dias_cobertura'] or 9999))

    return {
        'dias_analisis': dias_analisis,
        'filas': filas,
        'conteo_criticos': conteo_criticos,
        'conteo_reorden': conteo_reorden,
        'conteo_seguros': conteo_seguros,
    }


def obtener_valorizacion_por_plan_de_cuentas() -> dict:
    """
    Agrupa la valorización del inventario actual según las cuentas contables del Activo
    (Rubro 1.1.5 Bienes de Cambio) del Plan de Cuentas oficial.
    También computa el consumo histórico imputado en cuentas de costo agrícola (Rubro 4.2.1).
    """
    from collections import defaultdict
    from .models import Insumo, CategoriaInsumo
    from apps.finanzas.models import CuentaContable

    insumos = Insumo.objects.filter(activo=True).select_related(
        'categoria', 'cuenta_contable', 'categoria__cuenta_contable_activo', 'categoria__cuenta_contable_gasto'
    )

    grupos = defaultdict(lambda: {
        'cuenta': None,
        'total_valor_ars': Decimal('0.00'),
        'total_articulos': 0,
        'insumos': []
    })

    total_general = Decimal('0.00')

    for ins in insumos:
        cuenta = ins.cuenta_contable or ins.categoria.cuenta_contable_activo
        key = cuenta.id if cuenta else 0
        valor = round(Decimal(str(ins.stock_actual)) * Decimal(str(ins.costo_unitario_ars)), 2)
        total_general += valor

        grupos[key]['cuenta'] = cuenta
        grupos[key]['total_valor_ars'] += valor
        grupos[key]['total_articulos'] += 1
        grupos[key]['insumos'].append({
            'insumo': ins,
            'valor': valor,
            'cuenta_gasto': ins.categoria.cuenta_contable_gasto,
        })

    cuentas_lista = []
    for g in grupos.values():
        val = g['total_valor_ars']
        pct = round((val / total_general * 100) if total_general > 0 else Decimal('0.0'), 2)
        cuentas_lista.append({
            'cuenta': g['cuenta'],
            'total_valor_ars': val,
            'total_articulos': g['total_articulos'],
            'porcentaje': pct,
            'insumos': g['insumos'],
        })

    # Ordenar por mayor valor monetario
    cuentas_lista.sort(key=lambda x: x['total_valor_ars'], reverse=True)

    return {
        'total_general_ars': total_general,
        'cuentas': cuentas_lista,
    }


def crear_orden_compra_sugerida(
    insumos_cantidades: list,
    proveedor_id: int,
    finca_id: int,
    usuario=None
) -> dict:
    """
    Crea automáticamente una Orden de Compra en estado BORRADOR
    a partir de la lista de insumos y cantidades sugeridas de reabastecimiento.
    """
    from .models import OrdenDeCompra, ItemOrdenDeCompra, Insumo
    from apps.finanzas.models import CuentaCorriente
    from apps.core.models import Finca

    if not insumos_cantidades:
        return {'ok': False, 'mensaje': 'No se seleccionaron insumos para la orden de compra.'}

    proveedor = CuentaCorriente.objects.get(pk=proveedor_id)
    finca = Finca.objects.get(pk=finca_id)

    now = timezone.now()
    numero_oc = f"OC-SUG-{now.strftime('%y%m%d%H%M')}"

    with transaction.atomic():
        oc = OrdenDeCompra.objects.create(
            proveedor=proveedor,
            finca_destino=finca,
            numero=numero_oc,
            fecha_emision=now.date(),
            estado=OrdenDeCompra.Estado.BORRADOR,
            observaciones="Generada automáticamente por el Módulo de Reorden Analítico de Inventario.",
        )

        items_creados = 0
        for insumo_id, cant in insumos_cantidades:
            cant_dec = Decimal(str(cant))
            if cant_dec <= 0:
                continue
            ins = Insumo.objects.get(pk=insumo_id)
            ItemOrdenDeCompra.objects.create(
                orden=oc,
                insumo=ins,
                cantidad_solicitada=cant_dec,
                precio_unitario_estimado_ars=ins.costo_unitario_ars
            )
            items_creados += 1

        oc.recalcular_total()

    return {
        'ok': True,
        'mensaje': f"Orden de Compra {oc.numero} creada exitosamente con {items_creados} ítem(s).",
        'orden': oc,
    }


