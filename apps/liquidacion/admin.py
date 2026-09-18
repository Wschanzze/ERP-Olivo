from django.contrib import admin
from .models import PeriodoLiquidacion, LiquidacionEmpleado, ItemLiquidacion

class ItemLiquidacionInline(admin.TabularInline):
    model = ItemLiquidacion
    extra = 0

@admin.register(PeriodoLiquidacion)
class PeriodoLiquidacionAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'mes', 'ano', 'fecha_inicio', 'fecha_fin', 'estado')
    list_filter = ('ano', 'estado', 'tipo')

@admin.register(LiquidacionEmpleado)
class LiquidacionEmpleadoAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'periodo', 'dias_jornales_computados', 'total_bruto_remunerativo_ars', 'total_retenciones_ars', 'neto_a_cobrar_ars', 'estado')
    list_filter = ('periodo', 'estado')
    search_fields = ('empleado__apellido', 'empleado__nombre', 'empleado__legajo')
    inlines = [ItemLiquidacionInline]
