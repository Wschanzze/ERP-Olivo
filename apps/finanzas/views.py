from django.views.generic import TemplateView, ListView, CreateView
from django.urls import reverse_lazy
from django.shortcuts import render
from .models import Cuenta, CuentaCorriente, MovimientoFinanciero, Cheque
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
        ctx['active_tab'] = self.request.GET.get('tab', 'caja')
        return ctx


class CuentasListValoresView(ListView):
    model = Cuenta
    template_name = 'finanzas/partials/tab_caja.html'
    context_object_name = 'cuentas'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['movimientos'] = MovimientoFinanciero.objects.select_related('cuenta')[:15]
        return ctx


class MovimientoCreateView(CreateView):
    model = MovimientoFinanciero
    fields = ['cuenta', 'tipo', 'fecha', 'importe', 'moneda', 'concepto', 'comprobante_tipo', 'comprobante_nro', 'cuenta_corriente', 'centro_de_costo', 'finca']
    template_name = 'finanzas/partials/movimiento_form_modal.html'
    success_url = reverse_lazy('finanzas:dashboard')

    def form_valid(self, form):
        # Utilizar servicio explícito para impacto en cuenta y cuenta corriente
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
