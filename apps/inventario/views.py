from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.shortcuts import render
from .models import Insumo, MovimientoStock, Maquina, Remito, StockPorDeposito

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
