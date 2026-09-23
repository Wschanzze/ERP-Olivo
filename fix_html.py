import re

with open('templates/personal/orden_trabajo.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_js = """        .then(data => {
          if(data.status === 'ok') {
            if (data.orden_completada && this.ordenActiva) {
              this.ordenActiva.estado_raw = 'COMPLETADA';
              this.ordenActiva.estado = 'Completada';
            } else if (nuevoEstado === 'PENDIENTE' && this.ordenActiva && this.ordenActiva.estado_raw === 'COMPLETADA') {
              this.ordenActiva.estado_raw = 'EN_CURSO';
              this.ordenActiva.estado = 'En Curso';
            }
          } else {"""

new_js = """        .then(data => {
          if(data.status === 'ok') {
            if (this.ordenActiva && data.orden_estado_raw) {
              this.ordenActiva.estado_raw = data.orden_estado_raw;
              this.ordenActiva.estado = data.orden_estado_display;
            }
          } else {"""

content = content.replace(old_js, new_js)

with open('templates/personal/orden_trabajo.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("HTML actualizado")
