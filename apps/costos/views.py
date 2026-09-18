from django.views.generic import ListView
from django.db.models import Sum
from .models import CostoPorCentro
from apps.core.models import CentroDeCosto, Finca

class CostosDashboardView(ListView):
    model = CostoPorCentro
    template_name = 'costos/costos_dashboard.html'
    context_object_name = 'costos'

    def get_queryset(self):
        qs = CostoPorCentro.objects.select_related('centro_de_costo', 'finca', 'cuadro')
        finca_id = self.request.GET.get('finca')
        tipo = self.request.GET.get('tipo')
        if finca_id:
            qs = qs.filter(finca_id=finca_id)
        if tipo:
            qs = qs.filter(tipo_origen=tipo)
        return qs[:50]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        ctx['total_costos_ars'] = qs.aggregate(t=Sum('importe_ars'))['t'] or 0.00
        ctx['resumen_por_categoria'] = CostoPorCentro.objects.values('tipo_origen').annotate(total=Sum('importe_ars')).order_by('-total')
        ctx['centros_costo'] = CentroDeCosto.objects.filter(activo=True)
        return ctx
