from django.views.generic import ListView, CreateView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Insumo, MovimientoStock, Maquina, Remito, StockPorDeposito
from .models import OrdenDeCompra, ItemOrdenDeCompra, RecepcionMercaderia, ItemRecepcion
from apps.finanzas.models import CuentaCorriente

class InsumosListView(ListView):
    model = Insumo
    template_name = 'inventario/insumos_list.html'
    context_object_name = 'insumos'

    def get_queryset(self):
        qs = Insumo.objects.select_related('categoria').filter(activo=True)
        cat = self.request.GET.get('categoria')
        if cat:
            qs = qs.filter(categoria_id=cat)
        return qs


class InsumoCreateView(CreateView):
    model = Insumo
    fields = ['codigo', 'nombre', 'categoria', 'unidad_medida', 'principio_activo', 'stock_actual', 'stock_minimo', 'costo_unitario_ars', 'costo_unitario_usd']
    template_name = 'inventario/partials/insumo_form_modal.html'
    success_url = reverse_lazy('inventario:insumos_list')


class MovimientosStockListView(ListView):
    model = MovimientoStock
    template_name = 'inventario/movimientos_list.html'
    context_object_name = 'movimientos'

    def get_queryset(self):
        return MovimientoStock.objects.select_related('insumo', 'deposito', 'usuario')[:50]


class MovimientoStockCreateView(CreateView):
    model = MovimientoStock
    fields = ['insumo', 'deposito', 'deposito_destino', 'tipo', 'cantidad', 'costo_unitario', 'fecha', 'motivo', 'referencia_origen']
    template_name = 'inventario/partials/movimiento_form_modal.html'
    success_url = reverse_lazy('inventario:movimientos_list')

    def form_valid(self, form):
        form.instance.usuario = self.request.user if self.request.user.is_authenticated else None
        response = super().form_valid(form)
        # Actualizar stock de insumo
        insumo = form.cleaned_data['insumo']
        tipo = form.cleaned_data['tipo']
        cantidad = form.cleaned_data['cantidad']
        if tipo in (MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, MovimientoStock.TipoMovimiento.AJUSTE_POSITIVO):
            insumo.stock_actual += cantidad
        elif tipo in (MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO, MovimientoStock.TipoMovimiento.SALIDA_MERMA, MovimientoStock.TipoMovimiento.AJUSTE_NEGATIVO):
            insumo.stock_actual -= cantidad
        insumo.save(update_fields=['stock_actual', 'updated_at'])
        return response


class MaquinasListView(ListView):
    model = Maquina
    template_name = 'inventario/maquinas_list.html'
    context_object_name = 'maquinas'


class MaquinaCreateView(CreateView):
    model = Maquina
    fields = ['codigo', 'nombre', 'tipo', 'marca', 'modelo', 'ano_fabricacion', 'finca_asignada', 'horas_o_km_acumulados', 'estado']
    template_name = 'inventario/partials/maquina_form_modal.html'
    success_url = reverse_lazy('inventario:maquinas_list')


class RemitosListView(ListView):
    model = Remito
    template_name = 'inventario/remitos_list.html'
    context_object_name = 'remitos'


class RemitoCreateView(CreateView):
    model = Remito
    fields = ['numero', 'tipo', 'fecha', 'entidad_nombre', 'finca_origen', 'finca_destino', 'estado', 'observaciones']
    template_name = 'inventario/partials/remito_form_modal.html'
    success_url = reverse_lazy('inventario:remitos_list')


# --- Órdenes de Compra ---

class OrdenesCompraListView(ListView):
    model = OrdenDeCompra
    template_name = 'inventario/ordenes_compra_list.html'
    context_object_name = 'ordenes'

    def get_queryset(self):
        return OrdenDeCompra.objects.select_related('proveedor', 'finca_destino').prefetch_related('items').order_by('-fecha_emision')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['proveedores'] = CuentaCorriente.objects.filter(tipo_entidad='PROVEEDOR', activo=True)
        from apps.core.models import Finca
        ctx['fincas'] = Finca.objects.filter(activa=True)
        ctx['insumos'] = Insumo.objects.filter(activo=True)
        return ctx


class OrdenCompraCreateView(CreateView):
    model = OrdenDeCompra
    fields = ['proveedor', 'finca_destino', 'numero', 'fecha_emision', 'fecha_entrega_estimada', 'registrar_deuda_al_aprobar', 'observaciones']
    template_name = 'inventario/partials/oc_form_modal.html'
    success_url = reverse_lazy('inventario:ordenes_compra_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'inventario/partials/oc_row.html', {'orden': self.object})
        return response


class RecepcionCreateView(CreateView):
    model = RecepcionMercaderia
    fields = ['orden', 'deposito_destino', 'fecha_recepcion', 'numero_remito_proveedor', 'numero_factura_proveedor', 'registrar_deuda_al_confirmar', 'observaciones']
    template_name = 'inventario/recepcion_form.html'
    success_url = reverse_lazy('inventario:ordenes_compra_list')

    def get_initial(self):
        initial = super().get_initial()
        orden_id = self.request.GET.get('orden')
        if orden_id:
            initial['orden'] = orden_id
        from django.utils import timezone
        initial['fecha_recepcion'] = timezone.now().date()
        return initial

    def form_valid(self, form):
        form.instance.responsable = self.request.user if self.request.user.is_authenticated else None
        return super().form_valid(form)


class ConfirmarRecepcionView(View):
    def post(self, request, pk):
        from .services import confirmar_recepcion
        resultado = confirmar_recepcion(pk, usuario=request.user)
        if request.headers.get('HX-Request'):
            if resultado['ok']:
                return render(request, 'inventario/partials/recepcion_confirmada.html', {'resultado': resultado, 'pk': pk})
            else:
                from django.http import HttpResponse
                return HttpResponse(f'<div class="text-xs text-rose-700 font-semibold p-3 bg-rose-50 rounded-xl border border-rose-200">{resultado["mensaje"]}</div>')
        if resultado['ok']:
            messages.success(request, resultado['mensaje'])
        else:
            messages.error(request, resultado['mensaje'])
        return redirect('inventario:ordenes_compra_list')

