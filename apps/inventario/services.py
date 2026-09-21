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
