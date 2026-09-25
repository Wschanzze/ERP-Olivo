from django.views.generic import ListView, CreateView, View

from apps.core.excel_export import export_to_excel

from django.urls import reverse_lazy
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

import json
from django.views import View
from apps.personal.models import OrdenTrabajo, TareaOrdenTrabajo
from apps.campos.models import Cuadro
from apps.core.models import Finca
from .models import LoteDeCosecha, RegistroFenologico, EventoCuadro

class CuadrosListView(ListView):
    model = Cuadro
    template_name = 'campos/cuadros_list.html'
    context_object_name = 'cuadros'

    def get_queryset(self):
        qs = Cuadro.objects.select_related('finca').prefetch_related('registros_fenologicos').filter(activo=True)
        finca_id = self.request.GET.get('finca')
        variedad = self.request.GET.get('variedad')
        if finca_id:
            qs = qs.filter(finca_id=finca_id)
        if variedad:
            qs = qs.filter(variedad_olivo=variedad)
        return qs

    def get_template_names(self):
        if self.request.headers.get('HX-Request') and not self.request.headers.get('HX-Boosted'):
            return ['campos/partials/cuadros_table.html']
        return [self.template_name]


class CuadroCreateView(CreateView):
    model = Cuadro
    fields = ['finca', 'codigo', 'nombre', 'hectareas_netas', 'variedad_olivo', 'ano_plantacion', 'densidad_plantas_ha', 'marco_plantacion', 'sistema_riego', 'observaciones']
    template_name = 'campos/partials/cuadro_form_modal.html'
    success_url = reverse_lazy('campos:cuadros_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'campos/partials/cuadro_row.html', {'cuadro': self.object})
        return response


class CosechasListView(ListView):
    model = LoteDeCosecha
    template_name = 'campos/cosechas_list.html'
    context_object_name = 'cosechas'

    def get_queryset(self):
        return LoteDeCosecha.objects.select_related('cuadro', 'cuadro__finca').all()


class CosechaCreateView(CreateView):
    model = LoteDeCosecha
    fields = ['cuadro', 'campana', 'fecha_inicio', 'fecha_fin', 'kg_cosechados', 'destino', 'rendimiento_graso_porcentaje', 'calidad_observaciones', 'estado']
    template_name = 'campos/partials/cosecha_form_modal.html'
    success_url = reverse_lazy('campos:cosechas_list')


class RegistroFenologicoCreateView(CreateView):
    model = RegistroFenologico
    fields = ['cuadro', 'campana', 'fecha', 'fase_vegetativa', 'grados_dia_acumulados', 'temperatura_min', 'temperatura_max', 'riesgo_fitosanitario', 'observaciones']
    template_name = 'campos/partials/fenologia_form_modal.html'
    success_url = reverse_lazy('campos:cuadros_list')

    def get_initial(self):
        initial = super().get_initial()
        cuadro_id = self.request.GET.get('cuadro')
        if cuadro_id:
            initial['cuadro'] = cuadro_id
        initial['fecha'] = timezone.now().date()
        initial['campana'] = f"{timezone.now().year}/{timezone.now().year + 1}"
        return initial

    def form_valid(self, form):
        form.instance.responsable = self.request.user if self.request.user.is_authenticated else None
        super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            from django.http import HttpResponse
            response = HttpResponse('')
            response['HX-Trigger'] = 'refreshCuadros'
            return response
        return super().form_valid(form)


class EventoCuadroCreateView(CreateView):
    model = EventoCuadro
    fields = ['cuadro', 'campana', 'tipo_evento', 'fecha', 'descripcion']
    template_name = 'campos/partials/evento_form_modal.html'
    success_url = reverse_lazy('campos:cuadros_list')

    def get_initial(self):
        initial = super().get_initial()
        cuadro_id = self.request.GET.get('cuadro')
        if cuadro_id:
            initial['cuadro'] = cuadro_id
        initial['fecha'] = timezone.now().date()
        initial['campana'] = f"{timezone.now().year}/{timezone.now().year + 1}"
        return initial

    def form_valid(self, form):
        form.instance.responsable = self.request.user if self.request.user.is_authenticated else None
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            from django.http import HttpResponse
            return HttpResponse('<div class="text-xs text-emerald-700 font-semibold p-2">✓ Evento registrado</div>')
        return response


class OrdenTrabajoView(ListView):
    """Vista para gestionar Órdenes de Trabajo Semanales."""
    model = OrdenTrabajo
    template_name = 'campos/orden_trabajo.html'
    context_object_name = 'ordenes'

    def get_queryset(self):
        return OrdenTrabajo.objects.select_related('finca').prefetch_related(
            'tareas', 'tareas__finca', 'tareas__cuadro'
        ).order_by('-semana_inicio')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['fincas'] = Finca.objects.filter(activa=True)
        ctx['cuadros'] = Cuadro.objects.filter(activo=True).select_related('finca')
        
        # Pasar cuadros como JSON para el selector dinámico
        cuadros_list = [{'id': c.id, 'finca_id': c.finca_id, 'codigo': c.codigo} for c in ctx['cuadros']]
        ctx['cuadros_json'] = json.dumps(cuadros_list)
        
        # Historial de Órdenes en JSON para el Modal de Detalles
        ordenes_json = []
        for o in ctx['ordenes']:
            tareas = []
            for t in o.tareas.all():
                tareas.append({
                    'id': t.id,
                    'actividad': t.actividad,
                    'campo': t.finca.nombre if t.finca else 'N/A',
                    'cuadro': t.cuadro.codigo if t.cuadro else 'N/A',
                    'cantidad': float(t.cantidad),
                    'cantidad_completada': float(t.cantidad_completada),
                    'unidad': t.unidad,
                    'gente': t.gente,
                    'dias': t.dias,
                    'prioridad': t.get_prioridad_display(),
                    'estado': t.get_estado_display(),
                    'estado_raw': t.estado,
                    'linea_producto': t.linea_producto,
                    'notas': t.notas
                })
            ordenes_json.append({
                'id': o.id,
                'semana_inicio': o.semana_inicio.strftime('%d/%m/%Y'),
                'campo': o.finca.nombre if o.finca else 'Todos los campos',
                'observaciones': o.observaciones,
                'estado': o.get_estado_display(),
                'estado_raw': o.estado,
                'tareas': tareas
            })
        ctx['ordenes_json'] = json.dumps(ordenes_json)
        
        return ctx

class OrdenTrabajoGuardarView(View):
    """Guarda la orden de trabajo con sus tareas vía POST."""
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        
        # 1. Crear Orden
        orden = OrdenTrabajo.objects.create(
            semana_inicio=data.get('semana'),
            finca_id=data.get('finca') or None,
            observaciones=data.get('observaciones', '')
        )
        
        # 2. Crear Tareas
        tareas = data.get('tareas', [])
        for t in tareas:
            TareaOrdenTrabajo.objects.create(
                orden=orden,
                finca_id=t.get('finca') or None,
                cuadro_id=t.get('cuadro') or None,
                actividad=t.get('actividad', ''),
                cantidad=t.get('cantidad') or 0,
                unidad=t.get('unidad', ''),
                gente=t.get('gente') or None,
                dias=t.get('dias') or None,
                prioridad=t.get('prioridad', 'NORMAL'),
                linea_producto=t.get('linea_producto', ''),
                notas=t.get('notas', '')
            )
        
        return HttpResponse(json.dumps({'status': 'ok', 'orden_id': orden.id}), content_type='application/json')

class OrdenTrabajoCambiarEstadoView(View):
    """Cambia el estado de una orden o de una tarea específica."""
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        tipo = data.get('tipo')  # 'orden' o 'tarea'
        obj_id = data.get('id')
        nuevo_estado = data.get('estado')

        if tipo == 'orden':
            orden = OrdenTrabajo.objects.get(id=obj_id)
            orden.estado = nuevo_estado
            orden.save()
            return HttpResponse(json.dumps({'status': 'ok'}), content_type='application/json')
        elif tipo == 'tarea':
            tarea = TareaOrdenTrabajo.objects.get(id=obj_id)
            tarea.estado = nuevo_estado
            tarea.save()
            
            # Recalcular el estado de la orden
            orden = tarea.orden
            todas_completadas = not orden.tareas.exclude(estado='COMPLETADA').exists()
            hay_completadas = orden.tareas.filter(estado='COMPLETADA').exists()
            
            if todas_completadas:
                nuevo_estado_orden = 'COMPLETADA'
            elif hay_completadas:
                nuevo_estado_orden = 'EN_CURSO'
            else:
                nuevo_estado_orden = 'PLANIFICADA'
                
            if orden.estado != nuevo_estado_orden:
                orden.estado = nuevo_estado_orden
                orden.save()
                
            return HttpResponse(json.dumps({
                'status': 'ok', 
                'orden_estado_raw': orden.estado,
                'orden_estado_display': orden.get_estado_display()
            }), content_type='application/json')
            
        return HttpResponse(json.dumps({'status': 'error'}), status=400, content_type='application/json')

# ==========================================
# EXPORTADORES A EXCEL (CAMPOS)
# ==========================================

class ExportarCuadrosExcelView(View):
    def get(self, request, *args, **kwargs):
        qs = Cuadro.objects.select_related('finca').all()
        columnas = [
            ("Finca", lambda c: c.finca.nombre if c.finca else ""),
            ("Código Cuadro", "codigo"),
            ("Variedad", lambda c: c.get_variedad_olivo_display() if hasattr(c, 'get_variedad_olivo_display') else ""),
            ("Hectáreas Netas", "hectareas_netas"),
            ("Plantas Reales", "plantas_reales"),
            ("Sistema de Riego", lambda c: c.get_sistema_riego_display() if hasattr(c, 'get_sistema_riego_display') else ""),
            ("Estado Productivo", lambda c: c.get_estado_productivo_display() if hasattr(c, 'get_estado_productivo_display') else ""),
            ("Año de Plantación", "ano_plantacion"),
        ]
        return export_to_excel(qs, columnas, "Listado de Cuadros y Lotes", "cuadros")

class ExportarOrdenTrabajoExcelView(View):
    def get(self, request, *args, **kwargs):
        qs = TareaOrdenTrabajo.objects.select_related('finca', 'cuadro').all().order_by('-fecha_programada')
        columnas = [
            ("Fecha Programada", lambda o: o.fecha_programada.strftime("%d/%m/%Y") if o.fecha_programada else "-"),
            ("Finca", lambda o: o.finca.nombre if o.finca else "-"),
            ("Cuadro", lambda o: o.cuadro.codigo if o.cuadro else "General"),
            ("Tipo de Tarea", lambda o: o.get_tipo_tarea_display() if hasattr(o, 'get_tipo_tarea_display') else "-"),
            ("Estado", lambda o: o.get_estado_display() if hasattr(o, 'get_estado_display') else "-"),
            ("Costo Mano Obra Estimado", "costo_mano_obra_estimado"),
            ("Maquinaria", lambda o: o.maquina_asignada.nombre if hasattr(o, 'maquina_asignada') and o.maquina_asignada else "-"),
        ]
        return export_to_excel(qs, columnas, "Registro de Órdenes de Trabajo de Campo", "ordenes_trabajo")
