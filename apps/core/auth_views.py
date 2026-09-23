"""
Vistas de Autenticación y Administración de Usuarios del ERP Olivícola.
Integrado con Supabase Auth (GoTrue) y sincronización con el modelo Usuario local.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import Usuario, Finca
from .supabase_service import SupabaseAuthService


def login_view(request):
    """
    Pantalla de inicio de sesión.
    Autentica con Supabase Auth y sincroniza la sesión local de Django.
    Cuenta con respaldo (fallback) local contra la base de datos de Django.
    """
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    next_url = request.GET.get('next') or request.POST.get('next') or reverse('dashboard:index')
    error_msg = None

    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        password = request.POST.get('password', '')

        if not identifier or not password:
            error_msg = "Por favor, ingresa tu correo electrónico y tu contraseña."
        else:
            auth_success = False
            user = None

            # 1. Intentar autenticación con Supabase Auth
            if SupabaseAuthService.is_configured():
                success, user_data, err = SupabaseAuthService.sign_in(identifier, password)
                if success and user_data:
                    auth_success = True
                    supabase_uid = user_data.get('supabase_uid')
                    email = user_data.get('email', identifier)
                    metadata = user_data.get('user_metadata', {})

                    # Buscar o aprovisionar usuario local
                    user = Usuario.objects.filter(email__iexact=email).first()
                    if not user:
                        user = Usuario.objects.filter(supabase_uid=supabase_uid).first()

                    if not user:
                        # Crear usuario en Django
                        username = email.split('@')[0]
                        # Asegurar username único
                        base_username = username
                        counter = 1
                        while Usuario.objects.filter(username=username).exists():
                            username = f"{base_username}{counter}"
                            counter += 1

                        user = Usuario.objects.create(
                            username=username,
                            email=email,
                            first_name=metadata.get('first_name', ''),
                            last_name=metadata.get('last_name', ''),
                            rol=metadata.get('rol', Usuario.Rol.OPERARIO),
                            supabase_uid=supabase_uid,
                            is_active=True,
                        )

                    # Si es la cuenta administradora designada, asegurar privilegios totales
                    if email.lower() == 'josuugonzalezz@gmail.com':
                        user.rol = Usuario.Rol.ADMIN_GENERAL
                        user.is_staff = True
                        user.is_superuser = True

                    # Actualizar UID de Supabase si no estaba asignado
                    if supabase_uid and user.supabase_uid != supabase_uid:
                        user.supabase_uid = supabase_uid

                    # Sincronizar contraseña en Django para permitir fallback offline
                    user.set_password(password)
                    user.save()
            # 2. Respaldo (Fallback) local en caso de que Supabase no haya autenticado
            if not auth_success:
                user_local = authenticate(request, username=identifier, password=password)
                if not user_local:
                    # Intentar buscar por email si ingresó un correo
                    user_by_email = Usuario.objects.filter(email__iexact=identifier).first()
                    if user_by_email and user_by_email.check_password(password):
                        user_local = user_by_email

                if user_local and user_local.is_active:
                    user = user_local
                    auth_success = True
                    error_msg = None
                else:
                    error_msg = "El correo electrónico o la contraseña ingresados son incorrectos."

            # 3. Iniciar sesión si la autenticación fue exitosa
            if auth_success and user:
                if not hasattr(user, 'backend') or not user.backend:
                    user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, f"¡Bienvenido/a, {user.first_name or user.username}!")
                return redirect(next_url)

    context = {
        'next': next_url,
        'error_msg': error_msg,
    }
    return render(request, 'auth/login.html', context)


def logout_view(request):
    """Cierra la sesión activa y redirige al login."""
    logout(request)
    messages.info(request, "Has cerrado sesión correctamente.")
    return redirect('core:login')


@login_required
def usuarios_list_view(request):
    """
    Panel administrativo de gestión de usuarios del ERP (exclusivo ADMIN_GENERAL).
    Permite visualizar todos los usuarios, roles y estados.
    """
    if not (request.user.is_superuser or request.user.rol == Usuario.Rol.ADMIN_GENERAL):
        messages.error(request, "No tienes permisos de administrador para acceder a la gestión de usuarios.")
        return redirect('dashboard:index')

    usuarios = Usuario.objects.all().order_by('-is_active', 'rol', 'username')
    fincas = Finca.objects.filter(activa=True)

    stats = {
        'total': usuarios.count(),
        'activos': usuarios.filter(is_active=True).count(),
        'admins': usuarios.filter(rol=Usuario.Rol.ADMIN_GENERAL).count(),
        'campo': usuarios.filter(rol__in=[Usuario.Rol.RESPONSABLE_FINCA, Usuario.Rol.ENCARGADO_CAMPO, Usuario.Rol.INGENIERO_AGRONOMO]).count(),
        'finanzas': usuarios.filter(rol=Usuario.Rol.CONTABLE).count(),
    }

    context = {
        'usuarios': usuarios,
        'fincas': fincas,
        'roles': Usuario.Rol.choices,
        'stats': stats,
    }
    return render(request, 'auth/usuarios_list.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def usuario_crear_modal_view(request):
    """
    Modal para que el Administrador dé de alta nuevos usuarios con rol específico.
    Crea el usuario en Supabase Auth y lo sincroniza en Django.
    """
    if not (request.user.is_superuser or request.user.rol == Usuario.Rol.ADMIN_GENERAL):
        return HttpResponse("<div class='p-4 text-red-700'>No autorizado</div>", status=403)

    fincas = Finca.objects.filter(activa=True)

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        rol = request.POST.get('rol', Usuario.Rol.OPERARIO)
        finca_id = request.POST.get('finca') or None

        if not email or not password:
            return HttpResponse(
                "<div class='p-3 bg-red-100 text-red-700 rounded-lg text-sm'>El correo y la contraseña son obligatorios.</div>",
                status=400
            )

        if Usuario.objects.filter(email__iexact=email).exists():
            return HttpResponse(
                "<div class='p-3 bg-amber-100 text-amber-800 rounded-lg text-sm'>Ya existe un usuario con este correo electrónico.</div>",
                status=400
            )

        # 1. Crear usuario en Supabase Auth
        supabase_uid = None
        if SupabaseAuthService.is_configured():
            success, sb_data, err = SupabaseAuthService.admin_create_user(
                email=email,
                password=password,
                rol=rol,
                first_name=first_name,
                last_name=last_name,
                finca_id=finca_id
            )
            if not success:
                return HttpResponse(
                    f"<div class='p-3 bg-red-100 text-red-700 rounded-lg text-sm'>Error al crear en Supabase: {err}</div>",
                    status=400
                )
            supabase_uid = sb_data.get('supabase_uid')

        # 2. Crear usuario local en Django
        username = email.split('@')[0]
        base_username = username
        c = 1
        while Usuario.objects.filter(username=username).exists():
            username = f"{base_username}{c}"
            c += 1

        finca_obj = Finca.objects.filter(id=finca_id).first() if finca_id else None

        nuevo_usuario = Usuario.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            rol=rol,
            finca_predeterminada=finca_obj,
            supabase_uid=supabase_uid,
            is_active=True,
            is_staff=(rol == Usuario.Rol.ADMIN_GENERAL),
            is_superuser=(rol == Usuario.Rol.ADMIN_GENERAL),
        )
        nuevo_usuario.set_password(password)
        nuevo_usuario.save()

        messages.success(request, f"Usuario {email} ({nuevo_usuario.get_rol_display()}) creado exitosamente.")
        
        response = HttpResponse(status=200)
        response['HX-Refresh'] = 'true'
        return response

    context = {
        'fincas': fincas,
        'roles': Usuario.Rol.choices,
    }
    return render(request, 'auth/usuario_form_modal.html', context)


@login_required
@require_http_methods(['POST'])
def usuario_toggle_activo_view(request, pk):
    """Activa o desactiva el acceso a un usuario."""
    if not (request.user.is_superuser or request.user.rol == Usuario.Rol.ADMIN_GENERAL):
        return HttpResponse("No autorizado", status=403)

    target_user = get_object_or_404(Usuario, pk=pk)
    if target_user == request.user:
        messages.warning(request, "No puedes desactivar tu propia cuenta de Administrador.")
        return redirect('core:usuarios_list')

    target_user.is_active = not target_user.is_active
    target_user.save()

    estado = "activado" if target_user.is_active else "desactivado"
    messages.success(request, f"Usuario {target_user.email} {estado} correctamente.")
    return redirect('core:usuarios_list')


@login_required
@require_http_methods(['POST'])
def usuario_editar_rol_view(request, pk):
    """Modifica el rol y finca asignada de un usuario."""
    if not (request.user.is_superuser or request.user.rol == Usuario.Rol.ADMIN_GENERAL):
        return HttpResponse("No autorizado", status=403)

    target_user = get_object_or_404(Usuario, pk=pk)
    nuevo_rol = request.POST.get('rol')
    finca_id = request.POST.get('finca') or None

    if nuevo_rol in dict(Usuario.Rol.choices):
        target_user.rol = nuevo_rol
        target_user.is_staff = (nuevo_rol == Usuario.Rol.ADMIN_GENERAL)
        target_user.is_superuser = (nuevo_rol == Usuario.Rol.ADMIN_GENERAL)

    target_user.finca_predeterminada = Finca.objects.filter(id=finca_id).first() if finca_id else None
    target_user.save()

    messages.success(request, f"Permisos actualizados para {target_user.email} a {target_user.get_rol_display()}.")
    return redirect('core:usuarios_list')
