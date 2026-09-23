import re
import os

# 1. READ PERSONAL VIEWS
with open('apps/personal/views.py', 'r', encoding='utf-8') as f:
    personal_content = f.read()

# 2. EXTRACT ORDEN DE TRABAJO VIEWS
# Match OrdenTrabajoView, OrdenTrabajoGuardarView, OrdenTrabajoCambiarEstadoView
pattern = re.compile(r'(class OrdenTrabajoView\(.*?\n)(?=class \w+\(|$)', re.DOTALL)
match = pattern.search(personal_content)

if match:
    orden_views = match.group(1)
    # Extract until the end of the file or next unrelated class
    # Let's just find where to cut.
    # Actually, let's just do a string split since I know what classes are at the end.
    idx = personal_content.find("class OrdenTrabajoView")
    orden_views = personal_content[idx:]
    personal_content = personal_content[:idx]
    
    # Save personal_views
    with open('apps/personal/views.py', 'w', encoding='utf-8') as f:
        f.write(personal_content)
        
    # 3. ADD IMPORTS AND VIEWS TO CAMPOS VIEWS
    with open('apps/campos/views.py', 'r', encoding='utf-8') as f:
        campos_content = f.read()
        
    # We need to import the models and json in campos
    campos_imports = """
import json
from django.views import View
from apps.personal.models import OrdenTrabajo, TareaOrdenTrabajo
from apps.campos.models import Cuadro
"""
    # Just append at the top, or after existing imports
    campos_content = campos_content.replace("from .models import Cuadro", campos_imports + "from .models import Cuadro")
    
    # We need to change the template name in the views from 'personal/orden_trabajo.html' to 'campos/orden_trabajo.html'
    orden_views = orden_views.replace("'personal/orden_trabajo.html'", "'campos/orden_trabajo.html'")
    
    # Also fix url names in frontend JS? Not in views.py.
    
    with open('apps/campos/views.py', 'w', encoding='utf-8') as f:
        f.write(campos_content + "\n\n" + orden_views)

print("Views moved successfully!")
