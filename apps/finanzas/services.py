from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Cuenta, CuentaCorriente, MovimientoFinanciero

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
