from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from guardian.admin import GuardedModelAdmin
from .models import Empresa, Finca, CentroDeCosto, Usuario

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'cuit', 'moneda_principal', 'moneda_secundaria')

@admin.register(Finca)
class FincaAdmin(GuardedModelAdmin):
    list_display = ('nombre', 'codigo', 'superficie_total_ha', 'tipo_riego_principal', 'activa')
    list_filter = ('activa', 'tipo_riego_principal')
    search_fields = ('nombre', 'codigo', 'ubicacion')

@admin.register(CentroDeCosto)
class CentroDeCostoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo', 'finca', 'activo')
    list_filter = ('tipo', 'activo', 'finca')
    search_fields = ('codigo', 'nombre')

@admin.register(Usuario)
class CustomUsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'rol', 'finca_predeterminada', 'is_staff')
    list_filter = ('rol', 'is_staff', 'is_superuser', 'is_active', 'finca_predeterminada')
    fieldsets = UserAdmin.fieldsets + (
        ('Datos Agrícolas / Rol ERP', {'fields': ('rol', 'finca_predeterminada', 'telefono', 'avatar')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Datos Agrícolas / Rol ERP', {'fields': ('rol', 'finca_predeterminada', 'telefono')}),
    )
