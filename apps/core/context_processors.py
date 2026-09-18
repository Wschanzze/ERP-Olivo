from .models import Finca, Empresa

def erp_context(request):
    """Context processor para inyectar variables globales del ERP en los templates."""
    empresa = Empresa.objects.first()
    fincas = Finca.objects.filter(activa=True)
    
    # Finca seleccionada en sesión o por defecto del usuario
    finca_activa_id = request.session.get('active_finca_id')
    finca_activa = None
    if finca_activa_id:
        finca_activa = fincas.filter(id=finca_activa_id).first()
    if not finca_activa and request.user.is_authenticated and hasattr(request.user, 'finca_predeterminada'):
        finca_activa = request.user.finca_predeterminada
    if not finca_activa:
        finca_activa = fincas.first()

    return {
        'empresa_actual': empresa,
        'fincas_disponibles': fincas,
        'finca_activa': finca_activa,
    }
