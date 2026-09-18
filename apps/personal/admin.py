from django.contrib import admin
from .models import Empleado, RegistroAsistencia, Inscripcion

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('legajo', 'apellido', 'nombre', 'dni_cuil', 'rol_laboral', 'modalidad', 'finca_habitual', 'activo')
    list_filter = ('rol_laboral', 'modalidad', 'finca_habitual', 'activo')
    search_fields = ('legajo', 'apellido', 'nombre', 'dni_cuil')

@admin.register(RegistroAsistencia)
class RegistroAsistenciaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'empleado', 'finca', 'estado', 'horas_normales', 'horas_extras', 'jornal_computado')
    list_filter = ('estado', 'finca', 'fecha')
    search_fields = ('empleado__apellido', 'empleado__nombre', 'empleado__legajo')

@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ('apellido', 'nombre', 'dni_cuil', 'puesto_aspirado', 'finca_postulada', 'estado', 'apto_medico')
    list_filter = ('estado', 'finca_postulada', 'apto_medico')
    search_fields = ('apellido', 'nombre', 'dni_cuil')
