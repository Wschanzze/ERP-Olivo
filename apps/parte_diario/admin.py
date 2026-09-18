from django.contrib import admin
from .models import OrdenDeTrabajo, ParteDiario, ParteDiarioPersonal, ParteDiarioInsumo

class ParteDiarioPersonalInline(admin.TabularInline):
    model = ParteDiarioPersonal
    extra = 1

class ParteDiarioInsumoInline(admin.TabularInline):
    model = ParteDiarioInsumo
    extra = 1

@admin.register(OrdenDeTrabajo)
class OrdenDeTrabajoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cuadro', 'tipo_labor', 'fecha_programada', 'responsable', 'estado')
    list_filter = ('tipo_labor', 'estado', 'fecha_programada')
    search_fields = ('cuadro__codigo', 'cuadro__finca__nombre', 'instrucciones_tecnicas')

@admin.register(ParteDiario)
class ParteDiarioAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'finca', 'cuadro', 'supervisor', 'estado', 'fecha_cierre')
    list_filter = ('estado', 'finca', 'fecha')
    search_fields = ('cuadro__codigo', 'observaciones')
    inlines = [ParteDiarioPersonalInline, ParteDiarioInsumoInline]
