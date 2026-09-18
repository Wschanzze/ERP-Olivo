from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from .models import PeriodoLiquidacion, LiquidacionEmpleado
from .tasks import calcular_liquidacion_periodo_task

class PeriodosListView(ListView):
    model = PeriodoLiquidacion
    template_name = 'liquidacion/periodos_list.html'
    context_object_name = 'periodos'


class PeriodoDetailView(DetailView):
    model = PeriodoLiquidacion
    template_name = 'liquidacion/periodo_detail.html'
    context_object_name = 'periodo'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['liquidaciones'] = self.object.liquidaciones.select_related('empleado').prefetch_related('items').all()
        return ctx


class PeriodoCreateView(CreateView):
    model = PeriodoLiquidacion
    fields = ['mes', 'ano', 'tipo', 'fecha_inicio', 'fecha_fin', 'observaciones']
    template_name = 'liquidacion/partials/periodo_form_modal.html'
    success_url = reverse_lazy('liquidacion:periodos_list')


def lanzar_calculo_liquidacion_htmx(request, pk):
    """Dispara el cálculo asíncrono en Celery (o síncrono de respaldo en local)."""
    if request.method == 'POST':
        periodo = get_object_or_404(PeriodoLiquidacion, pk=pk)
        try:
            # Ejecutar tarea asíncrona de Celery
            calcular_liquidacion_periodo_task.delay(pk)
            messages.info(request, f"Cálculo de liquidación iniciado en segundo plano con Celery para el período {periodo}.")
        except Exception:
            # Si Redis/Celery worker no está corriendo localmente, ejecutar sincrónicamente como fallback
            calcular_liquidacion_periodo_task(pk)
            messages.success(request, f"Liquidación calculada con éxito a partir de las asistencias.")

        if request.headers.get('HX-Request'):
            return render(request, 'liquidacion/partials/periodo_status_badge.html', {'periodo': get_object_or_404(PeriodoLiquidacion, pk=pk)})
        return redirect('liquidacion:periodo_detail', pk=pk)
    return HttpResponse(status=405)
