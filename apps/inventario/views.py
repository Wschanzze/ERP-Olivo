from decimal import Decimal
from datetime import datetime
from django.views.generic import ListView, CreateView
from django.views import View
from django.urls import reverse_lazy, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import F, Q, Sum
from django.core.exceptions import ValidationError
from django.http import HttpResponse

from .models import (
    Insumo, CategoriaInsumo, Deposito, StockPorDeposito, MovimientoStock,
    Maquina, Remito, OrdenDeCompra, ItemOrdenDeCompra, RecepcionMercaderia, ItemRecepcion
)
from .forms import TransferenciaStockForm, AjusteStockForm, InsumoForm, GenerarOCSugeridaForm
from .services import (
    confirmar_recepcion, realizar_transferencia_stock, realizar_ajuste_stock, obtener_kardex_insumo,
    calcular_clasificacion_abc_inventario, calcular_matriz_cobertura_y_reorden,
    obtener_valorizacion_por_plan_de_cuentas, crear_orden_compra_sugerida
)
from apps.finanzas.models import CuentaCorriente



class InsumosListView(ListView):
    """
    Vista principal de gestión de inventario:
    - KPIs clave: Valor total, Insumos en alerta de stock, Cantidad de artículos.
    - Filtros por categoría, depósito y estado crítico.
    - Desglose multidepósito por artículo.
    """
    model = Insumo
    template_name = 'inventario/insumos_list.html'
    context_object_name = 'insumos'

    def get_queryset(self):
        qs = Insumo.objects.select_related('categoria').prefetch_related(
            'existencias_por_deposito__deposito'
        ).filter(activo=True)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(nombre__icontains=q) |
                Q(codigo__icontains=q) |
                Q(principio_activo__icontains=q)
            )

        categoria_id = self.request.GET.get('categoria')
        if categoria_id and categoria_id.isdigit():
            qs = qs.filter(categoria_id=int(categoria_id))

        deposito_id = self.request.GET.get('deposito')
        if deposito_id and deposito_id.isdigit():
            qs = qs.filter(
                existencias_por_deposito__deposito_id=int(deposito_id),
                existencias_por_deposito__cantidad__gt=0
            ).distinct()

        estado = self.request.GET.get('estado')
        if estado == 'critico':
            qs = qs.filter(stock_actual__lte=F('stock_minimo'))
        elif estado == 'normal':
            qs = qs.filter(stock_actual__gt=F('stock_minimo'))

        return qs.order_by('nombre')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        todos_insumos = Insumo.objects.filter(activo=True)

        total_valorizado = sum(i.valor_total_stock_ars for i in todos_insumos)
        total_criticos = todos_insumos.filter(stock_actual__lte=F('stock_minimo')).count()

        ctx['total_insumos_count'] = todos_insumos.count()
        ctx['total_valorizado_ars'] = total_valorizado
        ctx['total_criticos_count'] = total_criticos
        ctx['categorias'] = CategoriaInsumo.objects.all()
        ctx['depositos'] = Deposito.objects.filter(activo=True).select_related('finca')

        # Parámetros activos para el template
        ctx['filtro_q'] = self.request.GET.get('q', '')
        ctx['filtro_categoria'] = self.request.GET.get('categoria', '')
        ctx['filtro_deposito'] = self.request.GET.get('deposito', '')
        ctx['filtro_estado'] = self.request.GET.get('estado', '')

        return ctx


class InsumoCreateView(CreateView):
    model = Insumo
    form_class = InsumoForm
    template_name = 'inventario/partials/insumo_form_modal.html'
    success_url = reverse_lazy('inventario:insumos_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            messages.success(self.request, f"Insumo '{self.object.nombre}' creado exitosamente.")
            return render(self.request, 'inventario/partials/toast_refresh.html', {
                'mensaje': f"Insumo '{self.object.nombre}' creado exitosamente."
            })
        messages.success(self.request, f"Insumo '{self.object.nombre}' creado exitosamente.")
        return response


class InsumoKardexView(View):
    """
    Ficha de Kardex Físico y Valorado por Insumo:
    Muestra el histórico cronológico de entradas, salidas, transferencias y saldo progresivo.
    """
    def get(self, request, pk):
        insumo = get_object_or_404(Insumo.objects.select_related('categoria'), pk=pk)

        deposito_id = request.GET.get('deposito')
        deposito_id = int(deposito_id) if deposito_id and deposito_id.isdigit() else None

        fecha_desde_str = request.GET.get('desde')
        fecha_hasta_str = request.GET.get('hasta')

        fecha_desde = None
        fecha_hasta = None
        if fecha_desde_str:
            try:
                fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if fecha_hasta_str:
            try:
                fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        kardex = obtener_kardex_insumo(
            insumo_id=insumo.pk,
            deposito_id=deposito_id,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta
        )

        depositos = Deposito.objects.filter(activo=True).select_related('finca')

        context = {
            'insumo': insumo,
            'kardex': kardex,
            'depositos': depositos,
            'deposito_filtro': deposito_id,
            'fecha_desde': fecha_desde_str or '',
            'fecha_hasta': fecha_hasta_str or '',
        }

        # Si se solicita dentro de un modal HTMX
        if request.headers.get('HX-Request') and request.GET.get('modal'):
            return render(request, 'inventario/partials/kardex_modal.html', context)

        return render(request, 'inventario/kardex_insumo.html', context)


class MovimientosStockListView(ListView):
    """
    Registro completo de auditoría y trazabilidad de movimientos de stock.
    """
    model = MovimientoStock
    template_name = 'inventario/movimientos_list.html'
    context_object_name = 'movimientos'
    paginate_by = 40

    def get_queryset(self):
        qs = MovimientoStock.objects.select_related(
            'insumo', 'insumo__categoria', 'deposito', 'deposito_destino', 'usuario'
        ).order_by('-fecha')

        tipo = self.request.GET.get('tipo')
        if tipo:
            qs = qs.filter(tipo=tipo)

        insumo_id = self.request.GET.get('insumo')
        if insumo_id and insumo_id.isdigit():
            qs = qs.filter(insumo_id=int(insumo_id))

        deposito_id = self.request.GET.get('deposito')
        if deposito_id and deposito_id.isdigit():
            qs = qs.filter(
                Q(deposito_id=int(deposito_id)) | Q(deposito_destino_id=int(deposito_id))
            )

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(insumo__nombre__icontains=q) |
                Q(insumo__codigo__icontains=q) |
                Q(motivo__icontains=q) |
                Q(referencia_origen__icontains=q)
            )

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tipos_movimiento'] = MovimientoStock.TipoMovimiento.choices
        ctx['depositos'] = Deposito.objects.filter(activo=True).select_related('finca')
        ctx['insumos'] = Insumo.objects.filter(activo=True).order_by('nombre')
        ctx['filtro_tipo'] = self.request.GET.get('tipo', '')
        ctx['filtro_deposito'] = self.request.GET.get('deposito', '')
        ctx['filtro_insumo'] = self.request.GET.get('insumo', '')
        ctx['filtro_q'] = self.request.GET.get('q', '')
        return ctx


class TransferenciaStockCreateView(View):
    """
    Formulario modal HTMX para transferir stock entre depósitos.
    """
    def get(self, request):
        insumo_id = request.GET.get('insumo')
        initial = {}
        if insumo_id and insumo_id.isdigit():
            initial['insumo'] = insumo_id

        form = TransferenciaStockForm(initial=initial)
        return render(request, 'inventario/partials/transferencia_modal.html', {'form': form})

    def post(self, request):
        form = TransferenciaStockForm(request.POST)
        if form.is_valid():
            try:
                resultado = realizar_transferencia_stock(
                    insumo_id=form.cleaned_data['insumo'].id,
                    deposito_origen_id=form.cleaned_data['deposito_origen'].id,
                    deposito_destino_id=form.cleaned_data['deposito_destino'].id,
                    cantidad=form.cleaned_data['cantidad'],
                    motivo=form.cleaned_data['motivo'],
                    usuario=request.user if request.user.is_authenticated else None
                )
                messages.success(request, resultado['mensaje'])
                if request.headers.get('HX-Request'):
                    return render(request, 'inventario/partials/toast_refresh.html', {
                        'mensaje': resultado['mensaje']
                    })
                return redirect('inventario:insumos_list')
            except ValidationError as e:
                form.add_error(None, e.message if hasattr(e, 'message') else str(e))
            except Exception as e:
                form.add_error(None, f"Error inesperado al transferir: {str(e)}")

        return render(request, 'inventario/partials/transferencia_modal.html', {'form': form})


class AjusteStockCreateView(View):
    """
    Formulario modal HTMX para ajustes manuales (+ / - / merma) de stock.
    """
    def get(self, request):
        insumo_id = request.GET.get('insumo')
        initial = {}
        if insumo_id and insumo_id.isdigit():
            initial['insumo'] = insumo_id

        form = AjusteStockForm(initial=initial)
        return render(request, 'inventario/partials/ajuste_modal.html', {'form': form})

    def post(self, request):
        form = AjusteStockForm(request.POST)
        if form.is_valid():
            try:
                resultado = realizar_ajuste_stock(
                    insumo_id=form.cleaned_data['insumo'].id,
                    deposito_id=form.cleaned_data['deposito'].id,
                    tipo_ajuste=form.cleaned_data['tipo_ajuste'],
                    cantidad=form.cleaned_data['cantidad'],
                    costo_unitario=form.cleaned_data['costo_unitario'],
                    motivo=form.cleaned_data['motivo'],
                    usuario=request.user if request.user.is_authenticated else None
                )
                messages.success(request, resultado['mensaje'])
                if request.headers.get('HX-Request'):
                    return render(request, 'inventario/partials/toast_refresh.html', {
                        'mensaje': resultado['mensaje']
                    })
                return redirect('inventario:insumos_list')
            except ValidationError as e:
                form.add_error(None, e.message if hasattr(e, 'message') else str(e))
            except Exception as e:
                form.add_error(None, f"Error inesperado en ajuste: {str(e)}")

        return render(request, 'inventario/partials/ajuste_modal.html', {'form': form})


# Compatibilidad hacia atrás
MovimientoStockCreateView = AjusteStockCreateView


class AnalisisInventarioView(View):
    """
    Dashboard Analítico y Control Estratégico de Inventario (Fase 2):
    - Clasificación ABC de Pareto (80/15/5).
    - Matriz de Cobertura y Proyección de Días de Stock Restante.
    - Vinculación Contable con el Plan de Cuentas (Rubro 1.1.5 Bienes de Cambio).
    """
    def get(self, request):
        dias_analisis = request.GET.get('dias', '60')
        dias_analisis = int(dias_analisis) if dias_analisis.isdigit() else 60

        abc_data = calcular_clasificacion_abc_inventario()
        cobertura_data = calcular_matriz_cobertura_y_reorden(dias_analisis=dias_analisis)
        plan_cuentas_data = obtener_valorizacion_por_plan_de_cuentas()

        tab = request.GET.get('tab', 'abc')

        context = {
            'abc': abc_data,
            'cobertura': cobertura_data,
            'plan_cuentas': plan_cuentas_data,
            'tab_activa': tab,
            'dias_analisis': dias_analisis,
        }
        return render(request, 'inventario/analisis_stock.html', context)


class GenerarOCSugeridaView(View):
    """
    Formulario modal HTMX para crear una Orden de Compra formal en borrador
    a partir de una sugerencia del análisis de reorden.
    """
    def get(self, request):
        insumo_id = request.GET.get('insumo')
        insumo = get_object_or_404(Insumo, pk=insumo_id)
        cantidad_sug = request.GET.get('cantidad', '0')

        initial = {
            'insumo_id': insumo.id,
            'cantidad': Decimal(str(cantidad_sug)) if cantidad_sug else Decimal('0.00'),
        }
        form = GenerarOCSugeridaForm(initial=initial)
        return render(request, 'inventario/partials/oc_sugerida_modal.html', {
            'form': form,
            'insumo': insumo
        })

    def post(self, request):
        form = GenerarOCSugeridaForm(request.POST)
        if form.is_valid():
            insumo_id = form.cleaned_data['insumo_id']
            cantidad = form.cleaned_data['cantidad']
            proveedor = form.cleaned_data['proveedor']
            finca = form.cleaned_data['finca_destino']

            resultado = crear_orden_compra_sugerida(
                insumos_cantidades=[(insumo_id, cantidad)],
                proveedor_id=proveedor.id,
                finca_id=finca.id,
                usuario=request.user if request.user.is_authenticated else None
            )
            if resultado['ok']:
                messages.success(request, resultado['mensaje'])
                if request.headers.get('HX-Request'):
                    return render(request, 'inventario/partials/toast_refresh.html', {
                        'mensaje': resultado['mensaje']
                    })
                return redirect('inventario:ordenes_compra_list')
            else:
                form.add_error(None, resultado['mensaje'])

        insumo_id = request.POST.get('insumo_id')
        insumo = get_object_or_404(Insumo, pk=insumo_id) if insumo_id else None
        return render(request, 'inventario/partials/oc_sugerida_modal.html', {
            'form': form,
            'insumo': insumo
        })


# ──────────────────────────────────────────────────────────────────────────────
# MÁQUINAS Y REMITOS

# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# ÓRDENES DE COMPRA & RECEPCIONES
# ──────────────────────────────────────────────────────────────────────────────

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
        resultado = confirmar_recepcion(pk, usuario=request.user)
        if request.headers.get('HX-Request'):
            if resultado['ok']:
                return render(request, 'inventario/partials/recepcion_confirmada.html', {'resultado': resultado, 'pk': pk})
            else:
                return HttpResponse(f'<div class="text-xs text-rose-700 font-semibold p-3 bg-rose-50 rounded-xl border border-rose-200">{resultado["mensaje"]}</div>')
        if resultado['ok']:
            messages.success(request, resultado['mensaje'])
        else:
            messages.error(request, resultado['mensaje'])
        return redirect('inventario:ordenes_compra_list')
