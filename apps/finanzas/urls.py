from django.urls import path
from . import views

app_name = 'finanzas'

urlpatterns = [
    path('', views.FinanzasDashboardView.as_view(), name='dashboard'),
    path('caja/', views.CuentasListValoresView.as_view(), name='cuentas_list'),
    path('movimientos/crear/', views.MovimientoCreateView.as_view(), name='movimiento_create'),
    path('proveedores/', views.CuentasCorrientesProveedoresView.as_view(), name='proveedores_list'),
    path('clientes/', views.CuentasCorrientesClientesView.as_view(), name='clientes_list'),
    path('cheques/', views.ChequesListView.as_view(), name='cheques_list'),
    path('cheques/crear/', views.ChequeCreateView.as_view(), name='cheque_create'),
]
