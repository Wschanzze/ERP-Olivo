import re

with open('apps/personal/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_endpoint = """        elif tipo == 'tarea':
            tarea = TareaOrdenTrabajo.objects.get(id=obj_id)
            tarea.estado = nuevo_estado
            tarea.save()
            
            # Si todas las tareas están completadas, autocompletar la orden
            orden = tarea.orden
            todas_completadas = not orden.tareas.exclude(estado='COMPLETADA').exists()
            if todas_completadas and orden.estado != 'COMPLETADA':
                orden.estado = 'COMPLETADA'
                orden.save()
                
            return HttpResponse(json.dumps({'status': 'ok', 'orden_completada': todas_completadas}), content_type='application/json')"""

new_endpoint = """        elif tipo == 'tarea':
            tarea = TareaOrdenTrabajo.objects.get(id=obj_id)
            tarea.estado = nuevo_estado
            tarea.save()
            
            # Recalcular el estado de la orden
            orden = tarea.orden
            todas_completadas = not orden.tareas.exclude(estado='COMPLETADA').exists()
            hay_completadas = orden.tareas.filter(estado='COMPLETADA').exists()
            
            if todas_completadas:
                nuevo_estado_orden = 'COMPLETADA'
            elif hay_completadas:
                nuevo_estado_orden = 'EN_CURSO'
            else:
                nuevo_estado_orden = 'PLANIFICADA'
                
            if orden.estado != nuevo_estado_orden:
                orden.estado = nuevo_estado_orden
                orden.save()
                
            return HttpResponse(json.dumps({
                'status': 'ok', 
                'orden_estado_raw': orden.estado,
                'orden_estado_display': orden.get_estado_display()
            }), content_type='application/json')"""

content = content.replace(old_endpoint, new_endpoint)

with open('apps/personal/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Views actualizadas")
