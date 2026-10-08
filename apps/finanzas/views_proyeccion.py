from django.views.generic import TemplateView
from django.utils import timezone
from datetime import timedelta
from apps.finanzas.models import ComprobanteFiscal, Cheque
from apps.inventario.models import OrdenDeCompra
from django.db.models import Sum

class ProyeccionPagosView(TemplateView):
    template_name = 'finanzas/proyeccion_pagos.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        today = timezone.now().date()
        # Lunes y Domingo de la semana actual
        start_current_week = today - timedelta(days=today.weekday())
        end_current_week = start_current_week + timedelta(days=6)
        
        # Lunes y Domingo de la semana prxima
        start_next_week = end_current_week + timedelta(days=1)
        end_next_week = start_next_week + timedelta(days=6)

        def get_semana_data(start_date, end_date, is_past=False, is_future=False):
            # Filtros de fecha basados en el rango o abierto si es is_past/is_future
            
            # 1. Facturas a Pagar (ComprobanteFiscal)
            facturas_qs = ComprobanteFiscal.objects.filter(
                tipo_operacion='COMPRA',
                estado_pago__in=['PENDIENTE', 'PARCIAL']
            )
            if is_past:
                facturas_qs = facturas_qs.filter(fecha_vencimiento__lt=end_date)
            elif is_future:
                facturas_qs = facturas_qs.filter(fecha_vencimiento__gt=start_date)
            else:
                facturas_qs = facturas_qs.filter(fecha_vencimiento__range=(start_date, end_date))
            
            total_facturas = sum(f.saldo_pendiente for f in facturas_qs if hasattr(f, 'saldo_pendiente'))
            if total_facturas == 0:
                # Fallback si saldo_pendiente es mtodo no prop, asumiendo 'total'
                total_facturas = facturas_qs.aggregate(t=Sum('total'))['t'] or 0

            # 2. Cheques a Cubrir (Emitidos)
            cheques_qs = Cheque.objects.filter(
                tipo='EMITIDO',
                estado__in=['EN_CARTERA', 'ENTREGADO_PROVEEDOR']
            )
            if is_past:
                cheques_qs = cheques_qs.filter(fecha_cobro__lt=end_date)
            elif is_future:
                cheques_qs = cheques_qs.filter(fecha_cobro__gt=start_date)
            else:
                cheques_qs = cheques_qs.filter(fecha_cobro__range=(start_date, end_date))
                
            total_cheques = cheques_qs.aggregate(t=Sum('importe'))['t'] or 0

            # 3. Gastos Comprometidos (rdenes de Compra no facturadas/pendientes)
            ocs_qs = OrdenDeCompra.objects.filter(
                estado__in=['APROBADA', 'RECIBIDA_PARCIAL']
            )
            if is_past:
                ocs_qs = ocs_qs.filter(fecha_entrega_estimada__lt=end_date)
            elif is_future:
                ocs_qs = ocs_qs.filter(fecha_entrega_estimada__gt=start_date)
            else:
                ocs_qs = ocs_qs.filter(fecha_entrega_estimada__range=(start_date, end_date))
                
            total_ocs = ocs_qs.aggregate(t=Sum('total_estimado_ars'))['t'] or 0

            return {
                'start_date': start_date,
                'end_date': end_date,
                'facturas': facturas_qs.select_related('cuenta_corriente').order_by('fecha_vencimiento'),
                'total_facturas': total_facturas,
                'cheques': cheques_qs.order_by('fecha_cobro'),
                'total_cheques': total_cheques,
                'ocs': ocs_qs.select_related('proveedor').order_by('fecha_entrega_estimada'),
                'total_ocs': total_ocs,
                'total_semana': total_facturas + total_cheques + total_ocs
            }

        
        context['semana_actual'] = get_semana_data(None, end_current_week, is_past=True)
        context['semana_proxima'] = get_semana_data(start_next_week, end_next_week)
        context['semanas_futuras'] = get_semana_data(end_next_week, None, is_future=True)

        context['today'] = today
        return context
