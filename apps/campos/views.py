from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.shortcuts import render
from .models import Cuadro, LoteDeCosecha

class CuadrosListView(ListView):
    model = Cuadro
    template_name = 'campos/cuadros_list.html'
    context_object_name = 'cuadros'

    def get_queryset(self):
        qs = Cuadro.objects.select_related('finca').filter(activo=True)
        finca_id = self.request.GET.get('finca')
        variedad = self.request.GET.get('variedad')
        if finca_id:
            qs = qs.filter(finca_id=finca_id)
        if variedad:
            qs = qs.filter(variedad_olivo=variedad)
        return qs

    def get_template_names(self):
        # Si es petición HTMX parcial, renderizar únicamente la tabla
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
