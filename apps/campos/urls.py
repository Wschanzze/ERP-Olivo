from django.urls import path
from . import views

app_name = 'campos'

urlpatterns = [
    path('', views.CuadrosListView.as_view(), name='cuadros_list'),
    path('cuadros/crear/', views.CuadroCreateView.as_view(), name='cuadro_create'),
    path('cosechas/', views.CosechasListView.as_view(), name='cosechas_list'),
    path('cosechas/crear/', views.CosechaCreateView.as_view(), name='cosecha_create'),
]
