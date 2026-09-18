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
