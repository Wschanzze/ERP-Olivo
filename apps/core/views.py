from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Empresa

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, 'is_admin_general', False))

@login_required
@user_passes_test(is_admin)
def configuracion_empresa_view(request):
    empresa = Empresa.objects.first()
    if not empresa:
        empresa = Empresa.objects.create(
            razon_social='Mi Empresa S.A.',
            cuit='30-00000000-0',
            condicion_iva='Responsable Inscripto'
        )
        
    if request.method == 'POST':
        empresa.razon_social = request.POST.get('razon_social', '')
        empresa.nombre_fantasia = request.POST.get('nombre_fantasia', '')
        empresa.cuit = request.POST.get('cuit', '')
        empresa.direccion = request.POST.get('direccion', '')
        empresa.telefono = request.POST.get('telefono', '')
        empresa.email = request.POST.get('email', '')
        empresa.condicion_iva = request.POST.get('condicion_iva', '')
        empresa.ingresos_brutos = request.POST.get('ingresos_brutos', '')
        
        inicio = request.POST.get('inicio_actividades')
        if inicio:
            empresa.inicio_actividades = inicio
        else:
            empresa.inicio_actividades = None
            
        if 'logo' in request.FILES:
            empresa.logo = request.FILES['logo']
            
        empresa.save()
        messages.success(request, 'Configuración de la empresa actualizada con éxito.')
        return redirect('core:configuracion_empresa')

    return render(request, 'core/configuracion_empresa.html', {'empresa': empresa})
