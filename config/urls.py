from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Autenticación y Cuentas (Login, Logout, Usuarios)
    path('', include('apps.core.urls', namespace='core')),
    
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

from django.http import HttpResponseBadRequest, HttpResponseServerError
import sys
import traceback

def custom_bad_request(request, exception=None):
    error_msg = str(exception) if exception else "Solicitud incorrecta"
    host = request.headers.get('host', request.META.get('HTTP_HOST', 'desconocido'))
    return HttpResponseBadRequest(
        f"<h2>Error 400 - Bad Request</h2><p><strong>Detalle:</strong> {error_msg}</p><p><strong>Host:</strong> {host}</p>",
        content_type="text/html"
    )

def custom_server_error(request):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)) if exc_type else "No traceback disponible"
    html = f"""
    <!doctype html>
    <html lang="es">
    <head><title>500 - Error de Servidor</title></head>
    <body style="font-family: monospace; padding: 24px; background: #fafafa; color: #333;">
        <h2 style="color: #d32f2f;">Error 500 en Servidor (Vercel)</h2>
        <p><strong>Tipo:</strong> {exc_type.__name__ if exc_type else 'Desconocido'}</p>
        <p><strong>Mensaje:</strong> {exc_value}</p>
        <hr/>
        <h3>Detalle del Traceback:</h3>
        <pre style="background: #282c34; color: #abb2bf; padding: 16px; border-radius: 6px; overflow: auto; line-height: 1.4;">{tb_str}</pre>
    </body>
    </html>
    """
    return HttpResponseServerError(html, content_type="text/html")

handler400 = 'config.urls.custom_bad_request'
handler500 = 'config.urls.custom_server_error'
