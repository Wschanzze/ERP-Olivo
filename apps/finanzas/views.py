from django.views.generic import TemplateView, ListView, CreateView, DetailView, UpdateView
from django.urls import reverse_lazy
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal
import json
import datetime

from .models import Cuenta, CuentaCorriente, MovimientoFinanciero, Cheque, ConciliacionBancaria
from .services import registrar_movimiento_financiero


class FinanzasDashboardView(TemplateView):
    template_name = 'finanzas/finanzas_tabs.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cuentas'] = Cuenta.objects.filter(activa=True)
        ctx['proveedores'] = CuentaCorriente.objects.filter(tipo_entidad='PROVEEDOR', activo=True)
        ctx['clientes'] = CuentaCorriente.objects.filter(tipo_entidad='CLIENTE', activo=True)
        ctx['cheques'] = Cheque.objects.all()[:15]
        ctx['movimientos_recientes'] = MovimientoFinanciero.objects.select_related('cuenta', 'cuenta_corriente')[:20]
        ctx['active_tab'] = self.request.GET.get('tab', 'flujo')

        # Totales para flujo de caja
        hoy = timezone.now().date()
        inicio_mes = hoy.replace(day=1)
        ctx['total_ars'] = Cuenta.objects.filter(activa=True, moneda='ARS').aggregate(t=Sum('saldo_actual'))['t'] or Decimal('0')
        ctx['total_usd'] = Cuenta.objects.filter(activa=True, moneda='USD').aggregate(t=Sum('saldo_actual'))['t'] or Decimal('0')

        # Ingresos y egresos del mes actual
        movs_mes = MovimientoFinanciero.objects.filter(fecha__gte=inicio_mes)
        ctx['ingresos_mes'] = movs_mes.filter(tipo='INGRESO').aggregate(t=Sum('importe'))['t'] or Decimal('0')
        ctx['egresos_mes'] = movs_mes.filter(tipo='EGRESO').aggregate(t=Sum('importe'))['t'] or Decimal('0')
        ctx['transferencias_mes'] = movs_mes.filter(tipo='TRANSFERENCIA').aggregate(t=Sum('importe'))['t'] or Decimal('0')

        # Datos para el gráfico de barras: últimos 6 meses
        grafico_data = []
        for i in range(5, -1, -1):
            mes_ref = (hoy.replace(day=1) - datetime.timedelta(days=i * 28)).replace(day=1)
            siguiente = (mes_ref.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            ing = MovimientoFinanciero.objects.filter(fecha__gte=mes_ref, fecha__lt=siguiente, tipo='INGRESO').aggregate(t=Sum('importe'))['t'] or 0
            egr = MovimientoFinanciero.objects.filter(fecha__gte=mes_ref, fecha__lt=siguiente, tipo='EGRESO').aggregate(t=Sum('importe'))['t'] or 0
            grafico_data.append({
                'mes': mes_ref.strftime('%b'),
                'ingresos': float(ing),
                'egresos': float(egr),
            })
        ctx['grafico_data_json'] = json.dumps(grafico_data)

        # Conciliaciones recientes
        ctx['conciliaciones'] = ConciliacionBancaria.objects.select_related('cuenta').order_by('-fecha_extracto')[:10]
        return ctx


class CuentasListValoresView(ListView):
    model = Cuenta
    template_name = 'finanzas/partials/tab_caja.html'
    context_object_name = 'cuentas'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['movimientos'] = MovimientoFinanciero.objects.select_related('cuenta')[:15]
        return ctx


class CuentaCreateView(CreateView):
    model = Cuenta
    fields = ['nombre', 'tipo', 'moneda', 'banco_nombre', 'numero_cuenta', 'cbu_cvu', 'saldo_actual', 'empresa']
    template_name = 'finanzas/partials/cuenta_form_modal.html'
    success_url = reverse_lazy('finanzas:dashboard')

    def form_valid(self, form):
        cuenta = form.save()
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'finanzas/partials/cuenta_card.html', {'c': cuenta})
        return super().form_valid(form)


class CuentaUpdateView(UpdateView):
    model = Cuenta
    fields = ['nombre', 'tipo', 'moneda', 'banco_nombre', 'numero_cuenta', 'cbu_cvu', 'activa', 'empresa']
    template_name = 'finanzas/cuenta_edit.html'
    success_url = reverse_lazy('finanzas:dashboard')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cuenta'] = self.get_object()
        return ctx


class MovimientoCreateView(CreateView):
    model = MovimientoFinanciero
    fields = ['cuenta', 'tipo', 'fecha', 'importe', 'moneda', 'concepto', 'comprobante_tipo', 'comprobante_nro', 'cuenta_corriente', 'centro_de_costo', 'finca']
    template_name = 'finanzas/partials/movimiento_form_modal.html'
    success_url = reverse_lazy('finanzas:dashboard')

    def form_valid(self, form):
        movimiento = registrar_movimiento_financiero(
            cuenta=form.cleaned_data['cuenta'],
            tipo=form.cleaned_data['tipo'],
            fecha=form.cleaned_data['fecha'],
            importe=form.cleaned_data['importe'],
            concepto=form.cleaned_data['concepto'],
            moneda=form.cleaned_data['moneda'],
            comprobante_tipo=form.cleaned_data.get('comprobante_tipo', ''),
            comprobante_nro=form.cleaned_data.get('comprobante_nro', ''),
            cuenta_corriente=form.cleaned_data.get('cuenta_corriente'),
            centro_de_costo=form.cleaned_data.get('centro_de_costo'),
            finca=form.cleaned_data.get('finca'),
            usuario=self.request.user if self.request.user.is_authenticated else None
        )
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'finanzas/partials/movimiento_row.html', {'mov': movimiento})
        return super().form_valid(form)


class TransferenciaCreateView(CreateView):
    """Vista específica para registrar transferencias entre cuentas propias."""
    model = MovimientoFinanciero
    fields = ['cuenta', 'cuenta_destino', 'fecha', 'importe', 'moneda', 'concepto']
    template_name = 'finanzas/partials/transferencia_form_modal.html'
    success_url = reverse_lazy('finanzas:dashboard')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cuentas'] = Cuenta.objects.filter(activa=True)
        return ctx

    def form_valid(self, form):
        movimiento = registrar_movimiento_financiero(
            cuenta=form.cleaned_data['cuenta'],
            tipo=MovimientoFinanciero.TipoMovimiento.TRANSFERENCIA,
            fecha=form.cleaned_data['fecha'],
            importe=form.cleaned_data['importe'],
            concepto=form.cleaned_data['concepto'],
            moneda=form.cleaned_data['moneda'],
            cuenta_destino=form.cleaned_data.get('cuenta_destino'),
            usuario=self.request.user if self.request.user.is_authenticated else None
        )
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'finanzas/partials/movimiento_row.html', {'mov': movimiento})
        return redirect(self.success_url)


class CuentasCorrientesProveedoresView(ListView):
    model = CuentaCorriente
    template_name = 'finanzas/partials/tab_proveedores.html'
    context_object_name = 'proveedores'

    def get_queryset(self):
        return CuentaCorriente.objects.filter(tipo_entidad='PROVEEDOR', activo=True)


class CuentasCorrientesClientesView(ListView):
    model = CuentaCorriente
    template_name = 'finanzas/partials/tab_clientes.html'
    context_object_name = 'clientes'

    def get_queryset(self):
        return CuentaCorriente.objects.filter(tipo_entidad='CLIENTE', activo=True)


class ChequesListView(ListView):
    model = Cheque
    template_name = 'finanzas/partials/tab_cheques.html'
    context_object_name = 'cheques'


class ChequeCreateView(CreateView):
    model = Cheque
    fields = ['tipo', 'banco_emisor', 'numero', 'emisor_firmante', 'cuit_emisor', 'fecha_emision', 'fecha_cobro', 'importe', 'cuenta_bancaria_origen', 'cuenta_corriente', 'estado', 'observaciones']
    template_name = 'finanzas/partials/cheque_form_modal.html'
    success_url = reverse_lazy('finanzas:dashboard')


class ConciliacionListView(ListView):
    model = ConciliacionBancaria
    template_name = 'finanzas/partials/tab_conciliacion.html'
    context_object_name = 'conciliaciones'

    def get_queryset(self):
        return ConciliacionBancaria.objects.select_related('cuenta', 'usuario').order_by('-fecha_extracto')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cuentas_bancarias'] = Cuenta.objects.filter(activa=True, tipo='BANCO')
        return ctx


class ConciliacionCreateView(CreateView):
    model = ConciliacionBancaria
    fields = ['cuenta', 'fecha_extracto', 'saldo_extracto', 'observaciones']
    template_name = 'finanzas/partials/conciliacion_form_modal.html'
    success_url = reverse_lazy('finanzas:conciliaciones')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cuentas'] = Cuenta.objects.filter(activa=True)
        return ctx

    def form_valid(self, form):
        conciliacion = form.save(commit=False)
        conciliacion.saldo_sistema = conciliacion.cuenta.saldo_actual
        conciliacion.diferencia = conciliacion.saldo_extracto - conciliacion.saldo_sistema
        if self.request.user.is_authenticated:
            conciliacion.usuario = self.request.user
        conciliacion.save()
        return redirect(self.success_url)


class ConciliacionDetailView(DetailView):
    model = ConciliacionBancaria
    template_name = 'finanzas/conciliacion_detail.html'
    context_object_name = 'conciliacion'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        c = self.get_object()
        # Movimientos del período de la cuenta
        ctx['movimientos'] = MovimientoFinanciero.objects.filter(
            cuenta=c.cuenta,
            fecha__lte=c.fecha_extracto
        ).order_by('-fecha')[:50]
        ctx['ids_conciliados'] = set(c.movimientos_conciliados.values_list('id', flat=True))
        return ctx

    def post(self, request, *args, **kwargs):
        """Marcar/desmarcar movimientos como conciliados."""
        conciliacion = self.get_object()
        mov_ids = request.POST.getlist('movimientos_conciliados')
        conciliacion.movimientos_conciliados.set(mov_ids)
        # Actualizar diferencia
        total_conciliado = conciliacion.movimientos_conciliados.filter(tipo='INGRESO').aggregate(t=Sum('importe'))['t'] or 0
        total_conciliado -= float(conciliacion.movimientos_conciliados.filter(tipo='EGRESO').aggregate(t=Sum('importe'))['t'] or 0)
        if 'cerrar' in request.POST:
            conciliacion.estado = ConciliacionBancaria.EstadoConciliacion.CERRADA
        conciliacion.save()
        return redirect('finanzas:conciliacion_detail', pk=conciliacion.pk)
