from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from .models import Cuadro, LoteDeCosecha

@admin.register(Cuadro)
class CuadroAdmin(GuardedModelAdmin):
    list_display = ('codigo', 'nombre', 'finca', 'variedad_olivo', 'hectareas_netas', 'ano_plantacion', 'densidad_plantas_ha', 'activo')
    list_filter = ('finca', 'variedad_olivo', 'sistema_riego', 'activo')
    search_fields = ('codigo', 'nombre', 'finca__nombre')

@admin.register(LoteDeCosecha)
class LoteDeCosechaAdmin(admin.ModelAdmin):
    list_display = ('cuadro', 'campana', 'fecha_inicio', 'fecha_fin', 'kg_cosechados', 'destino', 'rendimiento_graso_porcentaje', 'estado')
    list_filter = ('campana', 'destino', 'estado', 'cuadro__finca')
    search_fields = ('cuadro__codigo', 'cuadro__nombre', 'campana')
