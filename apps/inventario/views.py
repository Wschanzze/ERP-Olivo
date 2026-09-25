from decimal import Decimal
from datetime import datetime
from django.views.generic import ListView, CreateView, DetailView
from django.views import View
from django.urls import reverse_lazy, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import F, Q, Sum, Count
from django.core.exceptions import ValidationError
from django.http import HttpResponse

from .models import (
    Insumo, CategoriaInsumo, Deposito, StockPorDeposito, MovimientoStock,
    Maquina, Remito, ItemRemito, OrdenDeCompra, ItemOrdenDeCompra, RecepcionMercaderia, ItemRecepcion
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
        
        # 1 consulta de agregación en SQL para total, valorización y bajo stock
        insumo_stats = Insumo.objects.filter(activo=True).aggregate(
            total_count=Count('id'),
            total_valor=Sum(F('stock_actual') * F('costo_unitario_ars')),
            total_criticos=Count('id', filter=Q(stock_actual__lte=F('stock_minimo')))
        )

        ctx['total_insumos_count'] = insumo_stats['total_count'] or 0
        ctx['total_valorizado_ars'] = insumo_stats['total_valor'] or Decimal('0.00')
        ctx['total_criticos_count'] = insumo_stats['total_criticos'] or 0
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

    def get_queryset(self):
        qs = Remito.objects.select_related('finca_origen', 'finca_destino').prefetch_related('items__insumo').order_by('-fecha', '-id')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(numero__icontains=q) |
                Q(entidad_nombre__icontains=q) |
                Q(transportista_nombre__icontains=q) |
                Q(patente_vehiculo__icontains=q) |
                Q(firma_nombre_receptor__icontains=q)
            )
        tipo = self.request.GET.get('tipo')
        if tipo:
            qs = qs.filter(tipo=tipo)
        firma = self.request.GET.get('firma')
        if firma == 'firmados':
            qs = qs.exclude(firma_digital='')
        elif firma == 'pendientes':
            qs = qs.filter(firma_digital='')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_remitos = Remito.objects.all()
        ctx['total_remitos'] = all_remitos.count()
        ctx['total_firmados'] = all_remitos.exclude(firma_digital='').count()
        ctx['total_pendientes'] = all_remitos.filter(firma_digital='').count()
        ctx['total_entradas'] = all_remitos.filter(tipo='ENTRADA_PROVEEDOR').count()
        from apps.core.models import Finca
        ctx['fincas'] = Finca.objects.filter(activa=True)
        ctx['insumos'] = Insumo.objects.filter(activo=True)
        from django.utils import timezone
        ctx['fecha_hoy'] = timezone.now().date()
        ctx['anio_actual'] = timezone.now().year
        ctx['proximo_nro'] = f"{all_remitos.count() + 1:04d}"
        return ctx


class RemitoCreateView(View):
    def post(self, request):
        try:
            numero = request.POST.get('numero', '').strip()
            tipo = request.POST.get('tipo', 'ENTRADA_PROVEEDOR')
            from django.utils import timezone
            fecha = request.POST.get('fecha') or timezone.now().date()
            entidad_nombre = request.POST.get('entidad_nombre', '').strip()
            finca_origen_id = request.POST.get('finca_origen') or None
            finca_destino_id = request.POST.get('finca_destino') or None
            transportista_nombre = request.POST.get('transportista_nombre', '').strip()
            patente_vehiculo = request.POST.get('patente_vehiculo', '').strip()
            observaciones = request.POST.get('observaciones', '').strip()

            if not numero:
                count = Remito.objects.count() + 1
                numero = f"REM-2026-{count:04d}"

            remito = Remito.objects.create(
                numero=numero,
                tipo=tipo,
                fecha=fecha,
                entidad_nombre=entidad_nombre,
                finca_origen_id=finca_origen_id,
                finca_destino_id=finca_destino_id,
                transportista_nombre=transportista_nombre,
                patente_vehiculo=patente_vehiculo,
                observaciones=observaciones,
                estado=Remito.EstadoRemito.BORRADOR
            )

            # Ítem inicial opcional
            item_insumo_id = request.POST.get('item_insumo_id')
            item_cantidad = request.POST.get('item_cantidad')
            if item_insumo_id and item_cantidad:
                try:
                    cant = Decimal(item_cantidad)
                    if cant > 0:
                        ItemRemito.objects.create(
                            remito=remito,
                            insumo_id=item_insumo_id,
                            cantidad_declarada=cant,
                            cantidad_recibida=cant
                        )
                except Exception:
                    pass

            messages.success(request, f"Remito {remito.numero} generado correctamente. Listo para firmar en móvil.")
            return redirect('inventario:remito_detalle', pk=remito.id)
        except Exception as e:
            messages.error(request, f"Error al crear el remito: {str(e)}")
            return redirect('inventario:remitos_list')


class RemitoDetailView(DetailView):
    model = Remito
    template_name = 'inventario/remito_detalle.html'
    context_object_name = 'remito'


class RemitoFirmarMobileView(View):
    def get(self, request, pk):
        remito = get_object_or_404(Remito.objects.prefetch_related('items__insumo'), pk=pk)
        return render(request, 'inventario/remito_firmar_mobile.html', {'remito': remito})

    def post(self, request, pk):
        remito = get_object_or_404(Remito, pk=pk)
        firma_base64 = request.POST.get('firma_digital', '').strip()
        nombre_receptor = request.POST.get('firma_nombre_receptor', '').strip()
        dni_receptor = request.POST.get('firma_dni_receptor', '').strip()
        aclaracion = request.POST.get('firma_aclaracion', '').strip()
        geoloc = request.POST.get('firma_geolocalizacion', '').strip()

        if not firma_base64 or not nombre_receptor or not dni_receptor:
            messages.error(request, "Es obligatorio completar Nombre, DNI y estampar la firma.")
            return render(request, 'inventario/remito_firmar_mobile.html', {'remito': remito})

        from django.utils import timezone
        remito.firma_digital = firma_base64
        remito.firma_nombre_receptor = nombre_receptor
        remito.firma_dni_receptor = dni_receptor
        remito.firma_aclaracion = aclaracion
        remito.firma_geolocalizacion = geoloc
        remito.firma_fecha_hora = timezone.now()
        remito.estado = Remito.EstadoRemito.CONFIRMADO
        remito.save()

        messages.success(request, "¡Recepción confirmada con éxito! La firma digital quedó registrada en el remito.")
        return redirect('inventario:remito_firmar', pk=remito.id)


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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['insumos'] = Insumo.objects.filter(activo=True).order_by('nombre')
        return ctx

    def form_valid(self, form):
        # Primero guardamos la cabecera (OrdenDeCompra)
        self.object = form.save()

        # Obtenemos los arrays de ítems enviados desde el form dinámico
        insumos = self.request.POST.getlist('insumo_id')
        cantidades = self.request.POST.getlist('cantidad')
        precios = self.request.POST.getlist('precio')

        # Procesamos y guardamos cada ítem
        for insumo_id, cantidad, precio in zip(insumos, cantidades, precios):
            if insumo_id and cantidad:
                try:
                    cant = Decimal(cantidad)
                    prec = Decimal(precio) if precio else Decimal('0.00')
                    if cant > 0:
                        ItemOrdenDeCompra.objects.create(
                            orden=self.object,
                            insumo_id=insumo_id,
                            cantidad_solicitada=cant,
                            precio_unitario_estimado_ars=prec
                        )
                except Exception:
                    pass

        # Recalculamos el total de la orden en base a los ítems guardados
        self.object.recalcular_total()

        if self.request.headers.get('HX-Request'):
            from django.http import HttpResponse
            redirect_url = reverse('inventario:ordenes_compra_list')
            response = HttpResponse(status=204)
            response['HX-Redirect'] = redirect_url
            return response
        return super().form_valid(form)


class OrdenCompraDetailView(DetailView):
    model = OrdenDeCompra
    template_name = 'inventario/orden_compra_detalle.html'
    context_object_name = 'orden'

    def get_queryset(self):
        return OrdenDeCompra.objects.select_related('proveedor', 'finca_destino').prefetch_related('items__insumo', 'recepciones')

class OrdenCompraPrintView(DetailView):
    model = OrdenDeCompra
    template_name = 'inventario/orden_compra_imprimir.html'
    context_object_name = 'orden'

    def get_queryset(self):
        return OrdenDeCompra.objects.select_related('proveedor', 'finca_destino').prefetch_related('items__insumo')

def aprobar_oc_htmx(request, pk):
    if request.method == 'POST':
        orden = get_object_or_404(OrdenDeCompra, pk=pk)
        if orden.estado == OrdenDeCompra.Estado.BORRADOR:
            orden.estado = OrdenDeCompra.Estado.APROBADA
            orden.save(update_fields=['estado'])
            messages.success(request, f"La Orden de Compra {orden.numero} ha sido aprobada exitosamente.")
        else:
            messages.error(request, "Solo se pueden aprobar órdenes en estado Borrador.")
        
        # Redirigir a la misma vista de detalle
        from django.http import HttpResponse
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('inventario:oc_detalle', args=[orden.pk])
        return response
    return HttpResponse(status=405)


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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        orden_id = self.request.GET.get('orden')
        if orden_id:
            ctx['orden_vinculada'] = get_object_or_404(OrdenDeCompra, pk=orden_id)
        return ctx

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

# ==========================================
# EXPORTADORES A EXCEL (INVENTARIO)
# ==========================================

class ExportarInsumosExcelView(View):
    def get(self, request, *args, **kwargs):
        insumos = Insumo.objects.all()
        columnas = [
            ("Código", "codigo"),
            ("Insumo / Artículo", "nombre"),
            ("Categoría", lambda i: i.categoria.nombre if i.categoria else ""),
            ("Stock Total", "stock_total"),
            ("Unidad", "unidad_medida"),
            ("Costo Unitario Ref. (ARS)", "costo_unitario_ars"),
        ]
        return export_to_excel(insumos, columnas, "Listado de Insumos y Artículos", "insumos")

class ExportarMovimientosExcelView(View):
    def get(self, request, *args, **kwargs):
        qs = MovimientoStock.objects.select_related('insumo', 'deposito_origen', 'deposito_destino').all().order_by('-fecha')
        columnas = [
            ("Fecha", lambda m: m.fecha.strftime("%d/%m/%Y %H:%M")),
            ("Tipo", "tipo_movimiento"),
            ("Insumo", lambda m: m.insumo.nombre),
            ("Cantidad", "cantidad"),
            ("Origen", lambda m: m.deposito_origen.nombre if m.deposito_origen else "-"),
            ("Destino", lambda m: m.deposito_destino.nombre if m.deposito_destino else "-"),
            ("Costo Total (ARS)", "costo_total_ars"),
            ("Responsable", lambda m: m.usuario.username if m.usuario else "Sistema"),
        ]
        return export_to_excel(qs, columnas, "Registro de Movimientos de Stock", "movimientos_stock")

class ExportarRemitosExcelView(View):
    def get(self, request, *args, **kwargs):
        qs = Remito.objects.all().order_by('-fecha')
        columnas = [
            ("Fecha", lambda r: r.fecha.strftime("%d/%m/%Y")),
            ("Número", "numero"),
            ("Tipo", "tipo_remito"),
            ("Punto Venta", "punto_venta"),
            ("Estado", "estado"),
            ("Finca Origen", lambda r: r.finca_origen.nombre if hasattr(r, 'finca_origen') and r.finca_origen else "-"),
            ("Transportista", "transportista_nombre"),
            ("Patente", "patente_vehiculo"),
        ]
        return export_to_excel(qs, columnas, "Registro de Remitos", "remitos")

class ExportarOrdenesExcelView(View):
    def get(self, request, *args, **kwargs):
        qs = OrdenCompra.objects.select_related('proveedor').all().order_by('-fecha_emision')
        columnas = [
            ("Fecha Emisión", lambda o: o.fecha_emision.strftime("%d/%m/%Y")),
            ("Número", "numero"),
            ("Proveedor", lambda o: o.proveedor.razon_social if o.proveedor else "-"),
            ("Estado", "estado"),
            ("Entrega Estimada", lambda o: o.fecha_entrega_estimada.strftime("%d/%m/%Y") if o.fecha_entrega_estimada else "-"),
            ("Total Estimado (ARS)", "total_estimado_ars"),
            ("Prioridad", "prioridad"),
        ]
        return export_to_excel(qs, columnas, "Registro de Órdenes de Compra", "ordenes_compra")
