from .models import Finca, Empresa

def erp_context(request):
    """Context processor para inyectar variables globales del ERP en los templates."""
    try:
        empresa = Empresa.objects.first()
        fincas = list(Finca.objects.filter(activa=True))
    except Exception:
        empresa = None
        fincas = []
    
    # Finca seleccionada en sesión o por defecto del usuario
    finca_activa = None
    try:
        finca_activa_id = request.session.get('active_finca_id') if hasattr(request, 'session') else None
        if finca_activa_id and fincas:
            finca_activa = next((f for f in fincas if f.id == finca_activa_id), None)
        if not finca_activa and getattr(request, 'user', None) and request.user.is_authenticated and hasattr(request.user, 'finca_predeterminada'):
            finca_activa = request.user.finca_predeterminada
        if not finca_activa and fincas:
            finca_activa = fincas[0]
    except Exception:
        finca_activa = None

    return {
        'empresa_actual': empresa,
        'fincas_disponibles': fincas,
        'finca_activa': finca_activa,
    }
