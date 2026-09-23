import re

with open('apps/personal/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the JSON serialization to include status fields
old_json_loop = """            for t in o.tareas.all():
                tareas.append({
                    'actividad': t.actividad,
                    'campo': t.finca.nombre if t.finca else 'N/A',
                    'cuadro': t.cuadro.codigo if t.cuadro else 'N/A',
                    'cantidad': float(t.cantidad),
                    'unidad': t.unidad,
                    'gente': t.gente,
                    'dias': t.dias,
                    'prioridad': t.get_prioridad_display(),
                    'linea_producto': t.linea_producto,
                    'notas': t.notas
                })
            ordenes_json.append({
                'id': o.id,
                'semana_inicio': o.semana_inicio.strftime('%d/%m/%Y'),
                'campo': o.finca.nombre if o.finca else 'Todos los campos',
                'observaciones': o.observaciones,
                'tareas': tareas
            })"""

new_json_loop = """            for t in o.tareas.all():
                tareas.append({
                    'id': t.id,
                    'actividad': t.actividad,
                    'campo': t.finca.nombre if t.finca else 'N/A',
                    'cuadro': t.cuadro.codigo if t.cuadro else 'N/A',
                    'cantidad': float(t.cantidad),
                    'cantidad_completada': float(t.cantidad_completada),
                    'unidad': t.unidad,
                    'gente': t.gente,
                    'dias': t.dias,
                    'prioridad': t.get_prioridad_display(),
                    'estado': t.get_estado_display(),
                    'estado_raw': t.estado,
                    'linea_producto': t.linea_producto,
                    'notas': t.notas
                })
            ordenes_json.append({
                'id': o.id,
                'semana_inicio': o.semana_inicio.strftime('%d/%m/%Y'),
                'campo': o.finca.nombre if o.finca else 'Todos los campos',
                'observaciones': o.observaciones,
                'estado': o.get_estado_display(),
                'estado_raw': o.estado,
                'tareas': tareas
            })"""

content = content.replace(old_json_loop, new_json_loop)

# 2. Add the endpoint view
new_endpoint = """
class OrdenTrabajoCambiarEstadoView(View):
    \"\"\"Cambia el estado de una orden o de una tarea específica.\"\"\"
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        tipo = data.get('tipo')  # 'orden' o 'tarea'
        obj_id = data.get('id')
        nuevo_estado = data.get('estado')

        if tipo == 'orden':
            orden = OrdenTrabajo.objects.get(id=obj_id)
            orden.estado = nuevo_estado
            orden.save()
            return HttpResponse(json.dumps({'status': 'ok'}), content_type='application/json')
        elif tipo == 'tarea':
            tarea = TareaOrdenTrabajo.objects.get(id=obj_id)
            tarea.estado = nuevo_estado
            tarea.save()
            
            # Si todas las tareas están completadas, autocompletar la orden
            orden = tarea.orden
            todas_completadas = not orden.tareas.exclude(estado='COMPLETADA').exists()
            if todas_completadas and orden.estado != 'COMPLETADA':
                orden.estado = 'COMPLETADA'
                orden.save()
                
            return HttpResponse(json.dumps({'status': 'ok', 'orden_completada': todas_completadas}), content_type='application/json')
            
        return HttpResponse(json.dumps({'status': 'error'}), status=400, content_type='application/json')
"""

content = content + new_endpoint

with open('apps/personal/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Views actualizadas")
