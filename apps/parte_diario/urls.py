from django.urls import path
from . import views

app_name = 'parte_diario'

urlpatterns = [
    path('', views.ParteDiarioView.as_view(), name='partes_list'),
    path('guardar/', views.ParteDiarioGuardarView.as_view(), name='parte_guardar'),
]
