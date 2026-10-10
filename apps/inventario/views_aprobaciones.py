from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.core.aprobaciones import obtener_adaptador, mover_documento


class TableroAprobacionesView(View):
    """
    Vista genérica para el Kanban de aprobaciones (OC u OP).
    """
    def get(self, request, tipo_doc):
        adaptador = obtener_adaptador(tipo_doc)
        
        # Filtros opcionales
        desde_str = request.GET.get('desde')
        hasta_str = request.GET.get('hasta')
        q = request.GET.get('q', '').strip()
        finca_id = request.GET.get('finca')

        desde = None
        hasta = None
        if desde_str:
            try:
                desde = timezone.datetime.strptime(desde_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if hasta_str:
            try:
                hasta = timezone.datetime.strptime(hasta_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        tablero = adaptador.construir_tablero(
            desde=desde,
            hasta=hasta,
            q=q,
            finca_id=finca_id,
            usuario=request.user
        )

        context = {
            'tipo_doc': tipo_doc,
            'adaptador': adaptador,
            'tablero': tablero,
            'filtro_desde': desde_str or '',
            'filtro_hasta': hasta_str or '',
            'filtro_q': q,
            'filtro_finca': finca_id or '',
        }
        
        # Necesitamos la lista de fincas para el filtro si es OC
        if tipo_doc.upper() == 'OC':
            from apps.core.models import Finca
            context['fincas'] = Finca.objects.filter(activa=True)
            
        return render(request, 'inventario/aprobaciones/tablero.html', context)


class SolicitarMovimientoAprobacionView(View):
    """
    Renderiza el modal de confirmación antes de aplicar un movimiento en el tablero.
    """
    def get(self, request, tipo_doc, pk, destino):
        adaptador = obtener_adaptador(tipo_doc)
        
        if not adaptador.puede_mover(request.user):
            return HttpResponse(
                '<div class="p-4 bg-red-50 text-red-700">No tienes permisos para aprobar o rechazar documentos.</div>', 
                status=403
            )

        doc = adaptador.obtener_para_actualizar(pk)
        columna_destino = adaptador.columna(destino)
        
        context = {
            'tipo_doc': tipo_doc,
            'pk': pk,
            'doc_referencia': adaptador.referencia(doc),
            'destino': columna_destino,
        }
        return render(request, 'inventario/aprobaciones/modal_confirmar.html', context)

    def post(self, request, tipo_doc, pk, destino):
        motivo = request.POST.get('motivo', '').strip()
        try:
            resultado = mover_documento(
                tipo_documento=tipo_doc,
                pk=pk,
                destino=destino,
                usuario=request.user,
                motivo=motivo
            )
            messages.success(request, resultado['mensaje'])
            
            # Para HTMX, devolvemos un código 204 con un header para refrescar o redirigir
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                # Recargar la página actual para ver el tablero actualizado
                response['HX-Refresh'] = 'true'
                return response
                
            return redirect('inventario:tablero_aprobaciones', tipo_doc=tipo_doc)
            
        except ValidationError as e:
            # Mostrar error en el mismo modal
            adaptador = obtener_adaptador(tipo_doc)
            columna_destino = adaptador.columna(destino)
            context = {
                'tipo_doc': tipo_doc,
                'pk': pk,
                'doc_referencia': adaptador.referencia(adaptador.obtener_para_actualizar(pk)),
                'destino': columna_destino,
                'error': e.message if hasattr(e, 'message') else str(e),
                'motivo': motivo,
            }
            return render(request, 'inventario/aprobaciones/modal_confirmar.html', context)
        except PermissionDenied as e:
            return HttpResponse(f'<div class="p-4 bg-red-50 text-red-700">{str(e)}</div>', status=403)
