from django.contrib import admin
from .models import CuentaContable, Cuenta, CuentaCorriente, MovimientoFinanciero, Cheque, TipoCambioMensual, CuadroResultado, LineaCuadroResultado

@admin.register(TipoCambioMensual)
class TipoCambioMensualAdmin(admin.ModelAdmin):
    list_display = ('ano', 'mes', 'tc', 'fuente', 'empresa', 'updated_at')
    list_filter = ('ano', 'empresa')
    ordering = ('-ano', '-mes')

@admin.register(CuadroResultado)
class CuadroResultadoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo_periodo', 'fecha_inicio', 'fecha_fin', 'moneda', 'tipo_cambio', 'ventas_totales', 'resultado_neto', 'estado')
    list_filter = ('tipo_periodo', 'moneda', 'estado', 'fecha_fin')
    search_fields = ('titulo', 'notas_gerencia')

@admin.register(CuentaContable)
class CuentaContableAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'clase', 'nivel', 'saldo_habitual', 'es_imputable', 'activa')
    list_filter = ('clase', 'saldo_habitual', 'es_imputable', 'nivel', 'activa')
    search_fields = ('codigo', 'nombre', 'nota')
    ordering = ('codigo',)

@admin.register(Cuenta)
class CuentaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'moneda', 'saldo_actual', 'cuenta_contable', 'activa')
    list_filter = ('tipo', 'moneda', 'activa')
    search_fields = ('nombre', 'banco_nombre', 'numero_cuenta')
    raw_id_fields = ('cuenta_contable',)

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
