from django.urls import path
from . import auth_views, views


app_name = 'core'

urlpatterns = [
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('usuarios/', auth_views.usuarios_list_view, name='usuarios_list'),
    path('usuarios/crear-modal/', auth_views.usuario_crear_modal_view, name='usuario_crear_modal'),
    path('usuarios/<int:pk>/toggle-activo/', auth_views.usuario_toggle_activo_view, name='usuario_toggle_activo'),
    path('usuarios/<int:pk>/editar-rol/', auth_views.usuario_editar_rol_view, name='usuario_editar_rol'),
    path('empresa/', views.configuracion_empresa_view, name='configuracion_empresa'),
]
