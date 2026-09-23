"""
Middleware de Control de Acceso y Autenticación del ERP Olivícola.
Garantiza que todas las rutas del ERP requieran sesión activa y restringe
el acceso a módulos sensibles según el rol del usuario (RBAC).
"""

from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import HttpResponse

class ERPAuthMiddleware:
    """
    Controla el acceso global al ERP:
    1. Redirecciona a /login/ si el usuario no ha iniciado sesión.
    2. Valida permisos por rol para cada módulo (/finanzas, /campos, etc.).
    3. Soporta redirecciones limpias para peticiones HTMX.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # 1. Rutas públicas excluidas de la protección
        RUTAS_PUBLICAS = [
            '/login/',
            '/logout/',
            '/recuperar-password/',
            '/admin/login/',
        ]
        
        PREFIX_PUBLICOS = [
            '/static/',
            '/media/',
            '/api/',
            '/favicon.ico',
        ]

        es_publica = path in RUTAS_PUBLICAS or any(path.startswith(prefix) for prefix in PREFIX_PUBLICOS)

        # 2. Si el usuario ya está autenticado y visita /login/, redirigir al Dashboard
        if request.user.is_authenticated and path == reverse('core:login'):
            return redirect('dashboard:index')

        # 3. Si no es ruta pública y el usuario NO está autenticado
        if not es_publica and not request.user.is_authenticated:
            login_url = reverse('core:login')
            next_url = request.get_full_path()
            target = f"{login_url}?next={next_url}"

            # Manejo especial para peticiones HTMX (evita que la pantalla de login se incruste en un div/modal)
            if request.headers.get('HX-Request') == 'true':
                response = HttpResponse(status=200)
                response['HX-Redirect'] = target
                return response

            return redirect(target)

        # 4. Control de Acceso por Módulos para usuarios autenticados
        if request.user.is_authenticated and not request.user.is_superuser:
            modulo = self._obtener_modulo_de_ruta(path)
            if modulo and hasattr(request.user, 'puede_acceder_modulo'):
                if not request.user.puede_acceder_modulo(modulo):
                    if request.headers.get('HX-Request') == 'true':
                        return HttpResponse(
                            "<div class='p-6 bg-red-50 text-red-800 rounded-2xl border border-red-200 text-sm font-semibold flex items-center space-x-3'>"
                            "<span>⛔</span><span>Acceso Restringido: Tu rol no tiene permisos para esta acción en el módulo "
                            f"<strong>{modulo.capitalize()}</strong>.</span></div>",
                            status=403
                        )
                    return render(
                        request, 
                        '403.html', 
                        {
                            'modulo_denegado': modulo.capitalize(),
                            'rol_usuario': request.user.get_rol_display(),
                        }, 
                        status=403
                    )

        return self.get_response(request)

    def _obtener_modulo_de_ruta(self, path: str) -> str:
        """Determina a qué módulo funcional del ERP corresponde la ruta."""
        if path.startswith('/finanzas/'):
            return 'finanzas'
        if path.startswith('/costos/'):
            return 'costos'
        if path.startswith('/liquidacion/'):
            return 'liquidacion'
        if path.startswith('/personal/'):
            return 'personal'
        if path.startswith('/campos/') or path.startswith('/parte-diario/'):
            return 'campo'
        if path.startswith('/inventario/'):
            return 'inventario'
        if path.startswith('/usuarios/'):
            return 'usuarios'
        return None
