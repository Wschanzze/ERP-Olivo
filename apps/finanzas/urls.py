from django.urls import path
from . import views

app_name = 'finanzas'

urlpatterns = [
    path('', views.FinanzasDashboardView.as_view(), name='dashboard'),
    path('caja/', views.CuentasListValoresView.as_view(), name='cuentas_list'),
    path('cuentas/crear/', views.CuentaCreateView.as_view(), name='cuenta_create'),
    path('cuentas/<int:pk>/editar/', views.CuentaUpdateView.as_view(), name='cuenta_edit'),
    path('movimientos/crear/', views.MovimientoCreateView.as_view(), name='movimiento_create'),
    path('transferencias/crear/', views.TransferenciaCreateView.as_view(), name='transferencia_create'),
    path('proveedores/', views.CuentasCorrientesProveedoresView.as_view(), name='proveedores_list'),
    path('clientes/', views.CuentasCorrientesClientesView.as_view(), name='clientes_list'),
    path('cheques/', views.ChequesListView.as_view(), name='cheques_list'),
    path('cheques/crear/', views.ChequeCreateView.as_view(), name='cheque_create'),
    path('conciliaciones/', views.ConciliacionListView.as_view(), name='conciliaciones'),
    path('conciliaciones/crear/', views.ConciliacionCreateView.as_view(), name='conciliacion_create'),
    path('conciliaciones/<int:pk>/', views.ConciliacionDetailView.as_view(), name='conciliacion_detail'),
]
