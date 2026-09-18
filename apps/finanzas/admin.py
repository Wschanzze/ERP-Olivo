from django.contrib import admin
from .models import Cuenta, CuentaCorriente, MovimientoFinanciero, Cheque

@admin.register(Cuenta)
class CuentaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'moneda', 'saldo_actual', 'banco_nombre', 'activa')
    list_filter = ('tipo', 'moneda', 'activa')
    search_fields = ('nombre', 'banco_nombre', 'numero_cuenta')

@admin.register(CuentaCorriente)
class CuentaCorrienteAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'tipo_entidad', 'cuit', 'saldo_actual', 'telefono', 'activo')
    list_filter = ('tipo_entidad', 'activo')
    search_fields = ('razon_social', 'cuit', 'email')

@admin.register(MovimientoFinanciero)
class MovimientoFinancieroAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo', 'cuenta', 'importe', 'moneda', 'concepto', 'cuenta_corriente', 'finca')
    list_filter = ('tipo', 'moneda', 'cuenta', 'fecha')
    search_fields = ('concepto', 'comprobante_nro', 'cuenta_corriente__razon_social')

@admin.register(Cheque)
class ChequeAdmin(admin.ModelAdmin):
    list_display = ('numero', 'tipo', 'banco_emisor', 'importe', 'fecha_cobro', 'estado', 'emisor_firmante')
    list_filter = ('tipo', 'estado', 'banco_emisor')
    search_fields = ('numero', 'emisor_firmante', 'cuit_emisor')
