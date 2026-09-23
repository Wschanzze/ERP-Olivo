import re

with open('templates/personal/orden_trabajo.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the table header
content = content.replace(
    """<th class="py-3.5 px-6 font-semibold">Observaciones</th>""",
    """<th class="py-3.5 px-6 font-semibold">Observaciones</th>
                <th class="py-3.5 px-6 font-semibold text-center">Estado</th>"""
)

# 2. Update the table body
old_td = """<td class="py-4 px-6 text-center">
                  <span class="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 rounded-full bg-oliva-50 text-oliva-700 font-bold text-xs border border-oliva-100">
                    {{ o.tareas.count }} Tareas
                  </span>
                </td>"""

new_td = """<td class="py-4 px-6 text-center">
                  {% if o.estado == 'PLANIFICADA' %}
                    <span class="inline-flex items-center px-2 py-1 rounded-md bg-slate-100 text-slate-600 text-xs font-bold border border-slate-200">Planificada</span>
                  {% elif o.estado == 'EN_CURSO' %}
                    <span class="inline-flex items-center px-2 py-1 rounded-md bg-sky-50 text-sky-700 text-xs font-bold border border-sky-200">En Curso</span>
                  {% elif o.estado == 'COMPLETADA' %}
                    <span class="inline-flex items-center px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 text-xs font-bold border border-emerald-200">Completada</span>
                  {% else %}
                    <span class="inline-flex items-center px-2 py-1 rounded-md bg-rose-50 text-rose-700 text-xs font-bold border border-rose-200">Cancelada</span>
                  {% endif %}
                </td>
                <td class="py-4 px-6 text-center">
                  <span class="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 rounded-full bg-oliva-50 text-oliva-700 font-bold text-xs border border-oliva-100">
                    {{ o.tareas.count }} Tareas
                  </span>
                </td>"""
content = content.replace(old_td, new_td)

# 3. Update Modal Header
old_modal_header = """<p class="text-xs text-slate-500 mt-0.5 font-medium" x-text="'Semana del: ' + (ordenActiva?.semana_inicio || '')"></p>"""
new_modal_header = """<div class="flex items-center gap-3 mt-1">
            <p class="text-xs text-slate-500 font-medium" x-text="'Semana del: ' + (ordenActiva?.semana_inicio || '')"></p>
            <span class="px-2 py-0.5 text-[10px] font-bold uppercase rounded-md border"
                  :class="{
                    'bg-slate-100 text-slate-600 border-slate-200': ordenActiva?.estado_raw === 'PLANIFICADA',
                    'bg-sky-50 text-sky-700 border-sky-200': ordenActiva?.estado_raw === 'EN_CURSO',
                    'bg-emerald-50 text-emerald-700 border-emerald-200': ordenActiva?.estado_raw === 'COMPLETADA',
                    'bg-rose-50 text-rose-700 border-rose-200': ordenActiva?.estado_raw === 'CANCELADA'
                  }" x-text="ordenActiva?.estado"></span>
          </div>"""
content = content.replace(old_modal_header, new_modal_header)

# 4. Update Modal Task List (Add Status Checkbox/Button)
old_task_header = """<span class="text-sm font-extrabold text-slate-800 flex items-center gap-1.5">
                          <span x-text="t.actividad || 'Tarea genérica'"></span>
                        </span>"""
new_task_header = """<div class="flex items-center gap-2">
                          <button type="button" @click="cambiarEstadoTarea(t)" class="w-5 h-5 rounded border flex items-center justify-center transition-colors shadow-2xs"
                                  :class="t.estado_raw === 'COMPLETADA' ? 'bg-emerald-500 border-emerald-600 text-white' : 'bg-white border-slate-300 text-transparent hover:border-emerald-400 hover:text-emerald-100'"
                                  :title="t.estado_raw === 'COMPLETADA' ? 'Marcar como pendiente' : 'Marcar como completada'">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
                          </button>
                          <span class="text-sm font-extrabold text-slate-800" :class="t.estado_raw === 'COMPLETADA' ? 'line-through opacity-60' : ''">
                            <span x-text="t.actividad || 'Tarea genérica'"></span>
                          </span>
                        </div>"""
content = content.replace(old_task_header, new_task_header)

# 5. Add JS functions
old_js = """// Acciones de Historial
    abrirDetalle(id) {"""
new_js = """// Funciones de Estado
    cambiarEstadoTarea(tarea) {
      const nuevoEstado = (tarea.estado_raw === 'COMPLETADA') ? 'PENDIENTE' : 'COMPLETADA';
      const backupEstado = tarea.estado_raw;
      tarea.estado_raw = nuevoEstado; // Optimistic UI
      tarea.estado = (nuevoEstado === 'COMPLETADA') ? 'Completada' : 'Pendiente';

      fetch('{% url "personal:orden_trabajo_estado" %}', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': '{{ csrf_token }}'
        },
        body: JSON.stringify({
          tipo: 'tarea',
          id: tarea.id,
          estado: nuevoEstado
        })
      })
      .then(res => res.json())
      .then(data => {
        if(data.status === 'ok') {
          if (data.orden_completada && this.ordenActiva) {
            this.ordenActiva.estado_raw = 'COMPLETADA';
            this.ordenActiva.estado = 'Completada';
          } else if (nuevoEstado === 'PENDIENTE' && this.ordenActiva && this.ordenActiva.estado_raw === 'COMPLETADA') {
            this.ordenActiva.estado_raw = 'EN_CURSO';
            this.ordenActiva.estado = 'En Curso';
          }
        } else {
          tarea.estado_raw = backupEstado;
          alert('Error al actualizar el estado de la tarea.');
        }
      }).catch(err => {
        tarea.estado_raw = backupEstado;
        console.error(err);
      });
    },

    // Acciones de Historial
    abrirDetalle(id) {"""
content = content.replace(old_js, new_js)


with open('templates/personal/orden_trabajo.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Template actualizado!")
