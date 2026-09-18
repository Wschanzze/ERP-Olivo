from django.urls import path
from . import views

app_name = 'personal'

urlpatterns = [
    path('', views.EmpleadosListView.as_view(), name='empleados_list'),
    path('empleados/crear/', views.EmpleadoCreateView.as_view(), name='empleado_create'),
    path('asistencia/', views.AsistenciaDiariaView.as_view(), name='asistencia_diaria'),
    path('asistencia/marcar/', views.marcar_asistencia_htmx, name='asistencia_marcar'),
    path('inscripciones/', views.InscripcionesListView.as_view(), name='inscripciones_list'),
    path('inscripciones/crear/', views.InscripcionCreateView.as_view(), name='inscripcion_create'),
]
