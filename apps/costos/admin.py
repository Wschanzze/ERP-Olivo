from django.contrib import admin
from .models import CostoPorCentro

@admin.register(CostoPorCentro)
class CostoPorCentroAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'centro_de_costo', 'finca', 'cuadro', 'tipo_origen', 'importe_ars', 'documento_origen_tipo')
    list_filter = ('tipo_origen', 'finca', 'centro_de_costo', 'fecha')
    search_fields = ('descripcion', 'centro_de_costo__nombre', 'centro_de_costo__codigo')
