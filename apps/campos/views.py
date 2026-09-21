from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from .models import Cuadro, LoteDeCosecha, RegistroFenologico, EventoCuadro

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
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'campos/partials/fenologia_badge.html', {'registro': self.object})
        return response


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
