from .models import Finca, Empresa

def erp_context(request):
    """Context processor para inyectar variables globales del ERP en los templates."""
    try:
        empresa = Empresa.objects.first()
        fincas = list(Finca.objects.filter(activa=True))
    except Exception:
        empresa = None
        fincas = []
    
    # En la nueva arquitectura, no hay una 'finca_activa' global en sesión.
    # El ERP funciona a nivel Empresa. Los filtros son locales por vista.
    finca_activa = None

    return {
        'empresa_actual': empresa,
        'fincas_disponibles': fincas,
        'finca_activa': finca_activa,
    }
