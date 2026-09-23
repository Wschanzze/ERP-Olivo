
import json
from django.views.generic import View, TemplateView
from django.urls import reverse
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from apps.parte_diario.models import ParteDiario, AvanceTarea
from apps.personal.models import OrdenTrabajo, TareaOrdenTrabajo
from apps.core.models import Finca

class ParteDiarioView(TemplateView):
    template_name = 'parte_diario/partes_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        # 1. Obtener Partes Diarios históricos
        partes_qs = ParteDiario.objects.select_related('finca', 'orden_trabajo').prefetch_related('avances_tareas__tarea').order_by('-fecha')
        
        # 2. Obtener Órdenes de Trabajo "En Curso" o "Planificadas" para el selector del nuevo parte
        ordenes_activas = OrdenTrabajo.objects.exclude(estado='COMPLETADA').order_by('-semana_inicio')
        
        # Preparar JSON de Órdenes (para que al seleccionar una, se carguen sus tareas)
        ordenes_json = []
        for o in ordenes_activas:
            tareas = []
            for t in o.tareas.all():
                tareas.append({
                    'id': t.id,
                    'actividad': t.actividad,
                    'campo': t.finca.nombre if t.finca else 'N/A',
                    'cuadro': t.cuadro.codigo if t.cuadro else 'N/A',
                    'meta': float(t.cantidad),
                    'completada': float(t.cantidad_completada),
                    'unidad': t.unidad
                })
            ordenes_json.append({
                'id': o.id,
                'semana_inicio': o.semana_inicio.strftime('%d/%m/%Y'),
                'observaciones': o.observaciones,
                'finca_id': o.finca_id,
                'tareas': tareas
            })
            
        ctx['ordenes_activas'] = ordenes_activas
        ctx['ordenes_json'] = json.dumps(ordenes_json)
        ctx['partes'] = partes_qs
        ctx['fincas'] = Finca.objects.filter(activa=True)
        return ctx

class ParteDiarioGuardarView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            
            # Crear Parte Diario
            parte = ParteDiario.objects.create(
                orden_trabajo_id=data.get('orden_trabajo_id'),
                finca_id=data.get('finca_id'),
                fecha=data.get('fecha'),
                observaciones=data.get('observaciones', ''),
                supervisor=request.user if request.user.is_authenticated else None
            )
            
            # Crear Avances
            avances = data.get('avances', [])
            for av in avances:
                tarea_id = av.get('tarea_id')
                cantidad = float(av.get('cantidad', 0))
                
                if cantidad > 0:
                    avance = AvanceTarea.objects.create(
                        parte_diario=parte,
                        tarea_id=tarea_id,
                        cantidad_avanzada=cantidad
                    )
                    
                    # Actualizar la meta en la tarea original
                    tarea = TareaOrdenTrabajo.objects.get(id=tarea_id)
                    tarea.cantidad_completada += cantidad
                    
                    # Logica auto-completar si llego a la meta
                    if tarea.cantidad > 0 and tarea.cantidad_completada >= tarea.cantidad:
                        if tarea.estado != 'COMPLETADA':
                            tarea.estado = 'COMPLETADA'
                    tarea.save()
                    
            # Recalcular el estado de la Orden (Opcional, o lo dejamos para la validación explícita)
            if parte.orden_trabajo:
                o = parte.orden_trabajo
                todas_completadas = not o.tareas.exclude(estado='COMPLETADA').exists()
                hay_completadas = o.tareas.filter(estado='COMPLETADA').exists()
                
                if todas_completadas:
                    nuevo_estado = 'COMPLETADA'
                elif hay_completadas:
                    nuevo_estado = 'EN_CURSO'
                else:
                    nuevo_estado = 'PLANIFICADA'
                    
                if o.estado != nuevo_estado:
                    o.estado = nuevo_estado
                    o.save()
                    
            return JsonResponse({'status': 'ok', 'parte_id': parte.id})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
