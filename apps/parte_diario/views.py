from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from .models import ParteDiario, OrdenDeTrabajo, ParteDiarioInsumo, ParteDiarioPersonal
from .services import confirmar_y_cerrar_parte_diario

class PartesDiariosListView(ListView):
    model = ParteDiario
    template_name = 'parte_diario/partes_list.html'
    context_object_name = 'partes'

    def get_queryset(self):
        qs = ParteDiario.objects.select_related('cuadro', 'finca', 'supervisor').all()
        finca_id = self.request.GET.get('finca')
        if finca_id:
            qs = qs.filter(finca_id=finca_id)
        return qs


class ParteDiarioDetailView(DetailView):
    model = ParteDiario
    template_name = 'parte_diario/parte_detail.html'
    context_object_name = 'parte'


class ParteDiarioCreateView(CreateView):
    model = ParteDiario
    fields = ['finca', 'cuadro', 'orden_de_trabajo', 'fecha', 'observaciones']
    template_name = 'parte_diario/partials/parte_form_modal.html'

    def form_valid(self, form):
        form.instance.supervisor = self.request.user if self.request.user.is_authenticated else None
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('parte_diario:parte_detail', kwargs={'pk': self.object.pk})


def cerrar_parte_htmx(request, pk):
    """Acción transaccional HTMX para cerrar un parte diario."""
    if request.method == 'POST':
        usuario = request.user if request.user.is_authenticated else None
        try:
            parte = confirmar_y_cerrar_parte_diario(pk, usuario=usuario)
            messages.success(request, f"Parte #{parte.id} cerrado con éxito. Stock descontado y costos imputados.")
        except Exception as e:
            messages.error(request, f"Error al cerrar el parte: {str(e)}")
            
        if request.headers.get('HX-Request'):
            return render(request, 'parte_diario/partials/parte_status_badge.html', {'parte': get_object_or_404(ParteDiario, pk=pk)})
        return redirect('parte_diario:parte_detail', pk=pk)
    return HttpResponse(status=405)


class OrdenesTrabajoListView(ListView):
    model = OrdenDeTrabajo
    template_name = 'parte_diario/ordenes_list.html'
    context_object_name = 'ordenes'


class OrdenTrabajoCreateView(CreateView):
    model = OrdenDeTrabajo
    fields = ['cuadro', 'tipo_labor', 'fecha_programada', 'fecha_limite', 'responsable', 'instrucciones_tecnicas', 'estado']
    template_name = 'parte_diario/partials/orden_form_modal.html'
    success_url = reverse_lazy('parte_diario:ordenes_list')


class RiegoCreateView(CreateView):
    """Crea o actualiza los datos de riego asociados a un parte diario."""
    from .models import ParteDiarioRiego
    model = ParteDiarioRiego
    fields = ['tipo_agua', 'horas_bomba', 'caudal_m3_hora', 'conductividad_electrica', 'temperatura_agua', 'observaciones_riego']
    template_name = 'parte_diario/partials/riego_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['parte_id'] = self.kwargs.get('parte_id')
        return ctx

    def form_valid(self, form):
        from .models import ParteDiario, ParteDiarioRiego
        parte_id = self.kwargs.get('parte_id')
        parte = get_object_or_404(ParteDiario, pk=parte_id)
        # Upsert: si ya existe un registro de riego para este parte, actualizarlo
        try:
            riego_existente = parte.datos_riego
            for field in self.fields:
                setattr(riego_existente, field, form.cleaned_data.get(field))
            riego_existente.save()
            riego = riego_existente
        except ParteDiarioRiego.DoesNotExist:
            form.instance.parte_diario = parte
            riego = form.save()
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'parte_diario/partials/riego_resumen.html', {'riego': riego})
        return redirect('parte_diario:parte_detail', pk=parte_id)
