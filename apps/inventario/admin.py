from django.contrib import admin
from .models import (
    CategoriaInsumo, Deposito, Insumo, StockPorDeposito, 
    MovimientoStock, Maquina, MantenimientoMaquina, Remito, ItemRemito
)

@admin.register(CategoriaInsumo)
class CategoriaInsumoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')

class StockPorDepositoInline(admin.TabularInline):
    model = StockPorDeposito
    extra = 0

@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'categoria', 'unidad_medida', 'stock_actual', 'stock_minimo', 'costo_unitario_ars', 'activo')
    list_filter = ('categoria', 'unidad_medida', 'activo')
    search_fields = ('codigo', 'nombre', 'principio_activo')
    inlines = [StockPorDepositoInline]

@admin.register(Deposito)
class DepositoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'finca', 'es_deposito_central', 'activo')
    list_filter = ('finca', 'es_deposito_central', 'activo')

@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo', 'insumo', 'deposito', 'cantidad', 'costo_unitario', 'motivo', 'referencia_origen')
    list_filter = ('tipo', 'deposito', 'fecha')
    search_fields = ('insumo__nombre', 'motivo', 'referencia_origen')

class MantenimientoInline(admin.TabularInline):
    model = MantenimientoMaquina
    extra = 0

@admin.register(Maquina)
class MaquinaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo', 'marca', 'finca_asignada', 'horas_o_km_acumulados', 'estado')
    list_filter = ('tipo', 'estado', 'finca_asignada')
    search_fields = ('codigo', 'nombre', 'marca')
    inlines = [MantenimientoInline]

class ItemRemitoInline(admin.TabularInline):
    model = ItemRemito
    extra = 1

@admin.register(Remito)
class RemitoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'tipo', 'fecha', 'entidad_nombre', 'finca_origen', 'finca_destino', 'estado')
    list_filter = ('tipo', 'estado', 'fecha')
    search_fields = ('numero', 'entidad_nombre')
    inlines = [ItemRemitoInline]
