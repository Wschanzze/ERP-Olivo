from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
from .models import Empleado, RegistroAsistencia, Inscripcion
from apps.core.models import Finca

class EmpleadosListView(ListView):
    model = Empleado
    template_name = 'personal/empleados_list.html'
    context_object_name = 'empleados'

    def get_queryset(self):
        qs = Empleado.objects.select_related('finca_habitual').all()
        finca_id = self.request.GET.get('finca')
        rol = self.request.GET.get('rol')
        if finca_id:
            qs = qs.filter(finca_habitual_id=finca_id)
        if rol:
            qs = qs.filter(rol_laboral=rol)
        return qs


class EmpleadoCreateView(CreateView):
    model = Empleado
    fields = ['legajo', 'nombre', 'apellido', 'dni_cuil', 'rol_laboral', 'modalidad', 'finca_habitual', 'valor_jornal_base_ars', 'valor_hora_extra_ars', 'fecha_ingreso', 'telefono', 'cbu_alias']
    template_name = 'personal/partials/empleado_form_modal.html'
    success_url = reverse_lazy('personal:empleados_list')


class AsistenciaDiariaView(ListView):
    """Panel de carga masiva de asistencia diaria por finca."""
    model = Empleado
    template_name = 'personal/asistencia_diaria.html'
    context_object_name = 'empleados'

    def get_queryset(self):
        finca_id = self.request.GET.get('finca')
        qs = Empleado.objects.filter(activo=True)
        if finca_id:
            qs = qs.filter(finca_habitual_id=finca_id)
        return qs.order_by('apellido', 'nombre')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fecha_str = self.request.GET.get('fecha')
        fecha = timezone.datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else timezone.now().date()
        ctx['fecha_seleccionada'] = fecha
        
        # Mapeo de asistencias del día
        asistencias = RegistroAsistencia.objects.filter(fecha=fecha)
        ctx['asistencias_dict'] = {a.empleado_id: a for a in asistencias}
        return ctx


def marcar_asistencia_htmx(request):
    """Endpoint HTMX para alternar asistencia al instante."""
    if request.method == 'POST':
        empleado_id = request.POST.get('empleado_id')
        fecha = request.POST.get('fecha')
        estado = request.POST.get('estado', 'PRESENTE')
        horas_normales = float(request.POST.get('horas_normales', 8.0))
        horas_extras = float(request.POST.get('horas_extras', 0.0))

        empleado = get_object_or_404(Empleado, pk=empleado_id)
        jornal = 1.0 if estado in ('PRESENTE', 'FERIADO_TRABAJADO') else 0.0

        asistencia, created = RegistroAsistencia.objects.update_or_create(
            empleado=empleado,
            fecha=fecha,
            defaults={
                'finca': empleado.finca_habitual,
                'estado': estado,
                'horas_normales': horas_normales,
                'horas_extras': horas_extras,
                'jornal_computado': jornal
            }
        )
        return render(request, 'personal/partials/asistencia_row_badge.html', {
            'asistencia': asistencia,
            'empleado': empleado,
            'fecha': fecha
        })
    return HttpResponse(status=405)


class InscripcionesListView(ListView):
    model = Inscripcion
    template_name = 'personal/inscripciones_list.html'
    context_object_name = 'inscripciones'


class InscripcionCreateView(CreateView):
    model = Inscripcion
    fields = ['dni_cuil', 'nombre', 'apellido', 'telefono', 'puesto_aspirado', 'finca_postulada', 'alta_temprana_afip_numero', 'apto_medico', 'observaciones']
    template_name = 'personal/partials/inscripcion_form_modal.html'
    success_url = reverse_lazy('personal:inscripciones_list')


# ──────────────────────────────────────────────────────────────────────────────
# QR FICHAJE
# ──────────────────────────────────────────────────────────────────────────────
import io
import qrcode
from django.views import View


class EmpleadoQRView(View):
    """Genera y sirve la imagen PNG del código QR único del empleado."""
    def get(self, request, pk):
        empleado = get_object_or_404(Empleado, pk=pk)
        # El UUID del empleado es el dato codificado en el QR
        qr_data = str(empleado.codigo_qr_uuid)
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='#3D4A2A', back_color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return HttpResponse(buffer.getvalue(), content_type='image/png')


class EmpleadoQRPageView(View):
    """Página que muestra el QR del empleado para imprimir."""
    def get(self, request, pk):
        empleado = get_object_or_404(Empleado, pk=pk)
        return render(request, 'personal/empleado_qr.html', {'empleado': empleado})


class FichajeQRView(View):
    """Endpoint de fichaje por QR — registra asistencia al escanear el QR del empleado."""
    def get(self, request):
        return render(request, 'personal/fichaje_qr.html', {})

    def post(self, request):
        uuid_str = request.POST.get('uuid', '').strip()
        if not uuid_str:
            return render(request, 'personal/fichaje_qr.html', {'error': 'UUID no recibido.'})
        try:
            empleado = Empleado.objects.get(codigo_qr_uuid=uuid_str, activo=True)
        except (Empleado.DoesNotExist, Exception):
            return render(request, 'personal/fichaje_qr.html', {'error': f'Código QR no reconocido: {uuid_str}'})
        hoy = timezone.now().date()
        finca_asistencia = empleado.finca_habitual or Finca.objects.filter(activa=True).first()
        asistencia, creada = RegistroAsistencia.objects.get_or_create(
            empleado=empleado,
            fecha=hoy,
            defaults={
                'finca': finca_asistencia,
                'estado': RegistroAsistencia.Estado.PRESENTE,
                'horas_normales': 8.0,
                'horas_extras': 0.0,
                'jornal_computado': 1.0,
                'observaciones': f"Fichaje QR móvil ({timezone.now().strftime('%H:%M:%S')} hs)"
            }
        )
        return render(request, 'personal/fichaje_qr.html', {
            'confirmacion': empleado,
            'creada': creada,
            'asistencia': asistencia,
        })

from .models import OrdenTrabajo, TareaOrdenTrabajo
from apps.campos.models import Cuadro
import json
from django.views import View

class OrdenTrabajoView(ListView):
    """Vista para gestionar Órdenes de Trabajo Semanales."""
    model = OrdenTrabajo
    template_name = 'personal/orden_trabajo.html'
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
            
            # Si todas las tareas están completadas, autocompletar la orden
            orden = tarea.orden
            todas_completadas = not orden.tareas.exclude(estado='COMPLETADA').exists()
            if todas_completadas and orden.estado != 'COMPLETADA':
                orden.estado = 'COMPLETADA'
                orden.save()
                
            return HttpResponse(json.dumps({'status': 'ok', 'orden_completada': todas_completadas}), content_type='application/json')
            
        return HttpResponse(json.dumps({'status': 'error'}), status=400, content_type='application/json')
