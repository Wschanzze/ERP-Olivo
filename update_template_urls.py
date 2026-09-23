import re

with open('templates/campos/orden_trabajo.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("personal:orden_trabajo_estado", "campos:orden_trabajo_estado")
content = content.replace("personal:orden_trabajo_guardar", "campos:orden_trabajo_guardar")

with open('templates/campos/orden_trabajo.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Template URLs updated!")
