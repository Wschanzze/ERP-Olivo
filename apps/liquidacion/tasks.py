from celery import shared_task
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from .models import PeriodoLiquidacion, LiquidacionEmpleado, ItemLiquidacion
from apps.personal.models import Empleado, RegistroAsistencia

@shared_task(bind=True)
def calcular_liquidacion_periodo_task(self, periodo_id: int):
    """
    Tarea asíncrona de Celery para calcular la liquidación de haberes 
    de todos los empleados a partir de sus asistencias registradas en el período.
    """
    periodo = PeriodoLiquidacion.objects.get(pk=periodo_id)
    periodo.estado = PeriodoLiquidacion.Estado.PROCESANDO
    periodo.save(update_fields=['estado', 'updated_at'])

    empleados = Empleado.objects.filter(activo=True)
    total_calculadas = 0

    for emp in empleados:
        with transaction.atomic():
            # 1. Obtener asistencias del período
            asistencias = RegistroAsistencia.objects.filter(
                empleado=emp,
                fecha__gte=periodo.fecha_inicio,
                fecha__lte=periodo.fecha_fin
            )
            
            # Sumar jornales y horas
            dias_jornales = sum(Decimal(str(a.jornal_computado)) for a in asistencias)
            horas_normales = sum(Decimal(str(a.horas_normales)) for a in asistencias.filter(estado='PRESENTE'))
            horas_extras = sum(Decimal(str(a.horas_extras)) for a in asistencias)

            # Si el empleado es jornalizado o mensual
            if emp.modalidad == Empleado.ModalidadContratacion.JORNAL_RURAL:
                bruto_jornales = dias_jornales * emp.valor_jornal_base_ars
                bruto_extras = horas_extras * emp.valor_hora_extra_ars
                bruto = bruto_jornales + bruto_extras
            else:
                # Mensualizado
                bruto = emp.valor_jornal_base_ars + (horas_extras * emp.valor_hora_extra_ars)

            # Retenciones de ley (11% Jubilación, 3% Ley 19032, 3% Obra Social Sindical UATRE)
            ret_jubilacion = round(bruto * Decimal('0.11'), 2)
            ret_inssjp = round(bruto * Decimal('0.03'), 2)
            ret_obra_social = round(bruto * Decimal('0.03'), 2)
            total_retenciones = ret_jubilacion + ret_inssjp + ret_obra_social
            neto = bruto - total_retenciones

            # Crear o actualizar liquidación
            liq, created = LiquidacionEmpleado.objects.update_or_create(
                periodo=periodo,
                empleado=emp,
                defaults={
                    'dias_jornales_computados': dias_jornales,
                    'horas_normales': horas_normales,
                    'horas_extras': horas_extras,
                    'total_bruto_remunerativo_ars': bruto,
                    'total_no_remunerativo_ars': Decimal('0.00'),
                    'total_retenciones_ars': total_retenciones,
                    'neto_a_cobrar_ars': neto,
                    'estado': LiquidacionEmpleado.Estado.CALCULADO
                }
            )

            # Borrar ítems previos y recrear
            liq.items.all().delete()

            # Ítem Básico Jornal
            ItemLiquidacion.objects.create(
                liquidacion=liq,
                codigo_concepto="JORNAL_BASE",
                descripcion=f"Jornales Rurales ({dias_jornales} días)",
                tipo=ItemLiquidacion.TipoConcepto.REMUNERATIVO,
                cantidad_o_porcentaje=dias_jornales,
                importe_ars=bruto_jornales if emp.modalidad == Empleado.ModalidadContratacion.JORNAL_RURAL else emp.valor_jornal_base_ars
            )

            # Ítem Horas Extras
            if horas_extras > 0:
                ItemLiquidacion.objects.create(
                    liquidacion=liq,
                    codigo_concepto="HORAS_EXTRAS",
                    descripcion=f"Horas Extras 50%/100% ({horas_extras}hs)",
                    tipo=ItemLiquidacion.TipoConcepto.REMUNERATIVO,
                    cantidad_o_porcentaje=horas_extras,
                    importe_ars=horas_extras * emp.valor_hora_extra_ars
                )

            # Ítems de Descuento
            ItemLiquidacion.objects.create(
                liquidacion=liq,
                codigo_concepto="JUBILACION_11",
                descripcion="Jubilación SIJP (11%)",
                tipo=ItemLiquidacion.TipoConcepto.RETENCION,
                cantidad_o_porcentaje=Decimal('11.00'),
                importe_ars=ret_jubilacion
            )
            ItemLiquidacion.objects.create(
                liquidacion=liq,
                codigo_concepto="LEY_19032_3",
                descripcion="INSSJyP Ley 19032 (3%)",
                tipo=ItemLiquidacion.TipoConcepto.RETENCION,
                cantidad_o_porcentaje=Decimal('3.00'),
                importe_ars=ret_inssjp
            )
            ItemLiquidacion.objects.create(
                liquidacion=liq,
                codigo_concepto="OS_UATRE_3",
                descripcion="Obra Social OSPRERA / UATRE (3%)",
                tipo=ItemLiquidacion.TipoConcepto.RETENCION,
                cantidad_o_porcentaje=Decimal('3.00'),
                importe_ars=ret_obra_social
            )

            total_calculadas += 1

    periodo.estado = PeriodoLiquidacion.Estado.CALCULADO
    periodo.save(update_fields=['estado', 'updated_at'])

    return {
        'periodo_id': periodo_id,
        'empleados_calculados': total_calculadas,
        'status': 'success'
    }
