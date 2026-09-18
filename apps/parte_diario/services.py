from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import ParteDiario, ParteDiarioInsumo, ParteDiarioPersonal
from apps.inventario.models import MovimientoStock, StockPorDeposito
from apps.costos.models import CostoPorCentro
from apps.core.models import CentroDeCosto

@transaction.atomic
def confirmar_y_cerrar_parte_diario(parte_diario_id: int, usuario=None) -> ParteDiario:
    """
    Servicio transaccional de cierre de Parte Diario.
    1. Descuenta existencias de insumos registrando MovimientoStock de SALIDA.
    2. Imputa CostoPorCentro de Insumos al Cuadro y Finca.
    3. Calcula e imputa CostoPorCentro de Mano de Obra al Cuadro y Finca.
    4. Cambia estado a CONFIRMADO_CERRADO.
    """
    parte = ParteDiario.objects.select_for_update().get(pk=parte_diario_id)
    if parte.estado == ParteDiario.Estado.CONFIRMADO_CERRADO:
        raise ValidationError("El Parte Diario ya se encuentra cerrado y confirmado.")

    # Obtener o asignar Centro de Costo productivo para la finca
    centro_costo = CentroDeCosto.objects.filter(
        finca=parte.finca, 
        tipo='PRODUCTIVO_CAMPO', 
        activo=True
    ).first()
    if not centro_costo:
        centro_costo = CentroDeCosto.objects.filter(activo=True).first()
        if not centro_costo:
            # Fallback en caso de que no exista aún centro de costo
            from apps.core.models import Empresa
            empresa = Empresa.objects.first()
            centro_costo = CentroDeCosto.objects.create(
                empresa=empresa,
                codigo=f"CC-PROD-{parte.finca.codigo}",
                nombre=f"Costos Productivos {parte.finca.nombre}",
                finca=parte.finca,
                tipo='PRODUCTIVO_CAMPO'
            )

    # 1 & 2. Procesar Insumos: Descuento de stock e imputación de costo
    for item in parte.insumos_utilizados.select_for_update().select_related('insumo', 'deposito_origen'):
        insumo = item.insumo
        costo_unitario = insumo.costo_unitario_ars
        costo_total = Decimal(str(item.cantidad_utilizada)) * costo_unitario

        item.costo_unitario_aplicado_ars = costo_unitario
        item.costo_total_ars = costo_total

        # Movimiento de Stock
        mov = MovimientoStock.objects.create(
            insumo=insumo,
            deposito=item.deposito_origen,
            tipo=MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO,
            cantidad=item.cantidad_utilizada,
            costo_unitario=costo_unitario,
            fecha=timezone.now(),
            motivo=f"Consumo en Parte #{parte.id} - Cuadro {parte.cuadro.codigo}",
            referencia_origen=f"ParteDiario #{parte.id}",
            usuario=usuario
        )
        item.movimiento_stock_generado = mov
        item.save()

        # Descontar stock global del insumo
        insumo.stock_actual -= item.cantidad_utilizada
        insumo.save(update_fields=['stock_actual', 'updated_at'])

        # Descontar existencia en depósito particular
        stock_dep, _ = StockPorDeposito.objects.get_or_create(
            deposito=item.deposito_origen,
            insumo=insumo,
            defaults={'cantidad': 0}
        )
        stock_dep.cantidad -= item.cantidad_utilizada
        stock_dep.save(update_fields=['cantidad', 'updated_at'])

        # Registrar Costo por Insumo
        if costo_total > 0:
            CostoPorCentro.objects.create(
                centro_de_costo=centro_costo,
                finca=parte.finca,
                cuadro=parte.cuadro,
                fecha=parte.fecha,
                importe_ars=costo_total,
                tipo_origen=CostoPorCentro.TipoOrigen.INSUMO,
                descripcion=f"Consumo {insumo.nombre} ({item.cantidad_utilizada} {insumo.unidad_medida}) en {parte.cuadro.codigo}",
                documento_origen_tipo="ParteDiario",
                documento_origen_id=parte.id
            )

    # 3. Procesar Mano de Obra: Cálculo de jornal e imputación de costo
    for item_pers in parte.personal_asignado.select_related('empleado'):
        emp = item_pers.empleado
        # Cálculo de costo de la jornada
        valor_hora = (emp.valor_jornal_base_ars / Decimal('8.0')) if emp.valor_jornal_base_ars > 0 else Decimal('0')
        costo_mo = (Decimal(str(item_pers.horas_normales)) * valor_hora) + (Decimal(str(item_pers.horas_extras)) * emp.valor_hora_extra_ars)
        
        item_pers.costo_jornal_calculado_ars = costo_mo
        item_pers.save(update_fields=['costo_jornal_calculado_ars', 'updated_at'])

        if costo_mo > 0:
            CostoPorCentro.objects.create(
                centro_de_costo=centro_costo,
                finca=parte.finca,
                cuadro=parte.cuadro,
                fecha=parte.fecha,
                importe_ars=costo_mo,
                tipo_origen=CostoPorCentro.TipoOrigen.MANO_DE_OBRA,
                descripcion=f"Mano de obra {emp.nombre_completo} ({item_pers.horas_normales}h) en {parte.cuadro.codigo}",
                documento_origen_tipo="ParteDiario",
                documento_origen_id=parte.id
            )

    # 4. Actualizar estado del Parte Diario
    parte.estado = ParteDiario.Estado.CONFIRMADO_CERRADO
    parte.fecha_cierre = timezone.now()
    parte.save(update_fields=['estado', 'fecha_cierre', 'updated_at'])

    return parte
