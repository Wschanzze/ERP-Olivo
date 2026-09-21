from django.urls import path
from . import views

app_name = 'liquidacion'

urlpatterns = [
    path('', views.PeriodosListView.as_view(), name='periodos_list'),
    path('crear/', views.PeriodoCreateView.as_view(), name='periodo_create'),
    path('<int:pk>/', views.PeriodoDetailView.as_view(), name='periodo_detail'),
    path('<int:pk>/calcular/', views.lanzar_calculo_liquidacion_htmx, name='periodo_calcular'),
    path('<int:pk>/recibo-pdf/', views.ReciboPDFView.as_view(), name='recibo_pdf'),
]
