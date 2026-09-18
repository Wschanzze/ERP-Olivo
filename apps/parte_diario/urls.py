from django.urls import path
from . import views

app_name = 'parte_diario'

urlpatterns = [
    path('', views.PartesDiariosListView.as_view(), name='partes_list'),
    path('crear/', views.ParteDiarioCreateView.as_view(), name='parte_create'),
    path('<int:pk>/', views.ParteDiarioDetailView.as_view(), name='parte_detail'),
    path('<int:pk>/cerrar/', views.cerrar_parte_htmx, name='parte_cerrar'),
    path('ordenes/', views.OrdenesTrabajoListView.as_view(), name='ordenes_list'),
    path('ordenes/crear/', views.OrdenTrabajoCreateView.as_view(), name='orden_create'),
]
