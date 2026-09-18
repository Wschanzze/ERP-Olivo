from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Módulos del ERP
    path('', include('apps.dashboard.urls', namespace='dashboard')),
    path('campos/', include('apps.campos.urls', namespace='campos')),
    path('finanzas/', include('apps.finanzas.urls', namespace='finanzas')),
    path('personal/', include('apps.personal.urls', namespace='personal')),
    path('parte-diario/', include('apps.parte_diario.urls', namespace='parte_diario')),
    path('inventario/', include('apps.inventario.urls', namespace='inventario')),
    path('costos/', include('apps.costos.urls', namespace='costos')),
    path('liquidacion/', include('apps.liquidacion.urls', namespace='liquidacion')),
    
    # API REST interna para Dashboard y futura App móvil
    path('api/v1/', include('apps.dashboard.api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
