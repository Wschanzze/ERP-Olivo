import re

with open('templates/personal/orden_trabajo.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the frontend select in Tareas
old_finca_select = """                    <div>
                      <label class="block text-[10px] font-bold text-slate-500 uppercase mb-1">Campo</label>
                      <select x-model="tarea.finca" class="w-full text-xs border-slate-200 rounded-lg focus:border-oliva-500 bg-slate-50">
                        <option value="">— Seleccionar —</option>
                        {% for f in fincas %}
                          <option value="{{ f.id }}">{{ f.nombre }}</option>
                        {% endfor %}
                      </select>
                    </div>"""

new_finca_select = """                    <div>
                      <label class="block text-[10px] font-bold text-slate-500 uppercase mb-1">Campo <span x-show="finca !== ''" class="lowercase text-[9px] font-normal text-slate-400">(Heredado)</span></label>
                      <select x-model="tarea.finca" 
                              :disabled="finca !== ''"
                              :class="{'bg-slate-100 text-slate-400 border-slate-200 opacity-80 cursor-not-allowed': finca !== ''}"
                              class="w-full text-xs border-slate-200 rounded-lg focus:border-oliva-500 bg-slate-50">
                        <option value="">— Seleccionar —</option>
                        {% for f in fincas %}
                          <option value="{{ f.id }}">{{ f.nombre }}</option>
                        {% endfor %}
                      </select>
                    </div>"""

content = content.replace(old_finca_select, new_finca_select)


# 2. Update the Alpine init and logic
old_alpine = """    // Para el modal
    modalDetalle: false,
    ordenActiva: null,

    agregarTarea() {
      this.tareas.push({ id: Date.now(), finca: '', cuadro: '', actividad: '', cantidad: 0, unidad: '', gente: '', dias: '', prioridad: 'NORMAL', linea_producto: '', notas: '' });
    },"""

new_alpine = """    // Para el modal
    modalDetalle: false,
    ordenActiva: null,
    
    init() {
      this.$watch('finca', (val) => {
        if (val !== '') {
          this.tareas.forEach(t => {
            t.finca = val;
            // Opcional: limpiar cuadro si no pertenece a la finca nueva
            const cuadroValido = this.getCuadrosForFinca(val).find(c => String(c.id) === String(t.cuadro));
            if (!cuadroValido) t.cuadro = '';
          });
        }
      });
    },

    agregarTarea() {
      this.tareas.push({ id: Date.now(), finca: this.finca || '', cuadro: '', actividad: '', cantidad: 0, unidad: '', gente: '', dias: '', prioridad: 'NORMAL', linea_producto: '', notas: '' });
    },"""

content = content.replace(old_alpine, new_alpine)

with open('templates/personal/orden_trabajo.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Modificaciones listas")
