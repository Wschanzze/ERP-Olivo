import re

# UPDATE PERSONAL URLS
with open('apps/personal/urls.py', 'r', encoding='utf-8') as f:
    personal_urls = f.read()

personal_urls = re.sub(r"\s*# Órdenes de Trabajo.*?(?=\])", "", personal_urls, flags=re.DOTALL)
personal_urls = re.sub(r"\s*path\('asistencia/orden-trabajo/.*?(?=\])", "", personal_urls, flags=re.DOTALL)

with open('apps/personal/urls.py', 'w', encoding='utf-8') as f:
    f.write(personal_urls)

# UPDATE CAMPOS URLS
with open('apps/campos/urls.py', 'r', encoding='utf-8') as f:
    campos_urls = f.read()

new_urls = """    path('eventos/crear/', views.EventoCuadroCreateView.as_view(), name='evento_create'),
    
    # Órdenes de Trabajo
    path('orden-trabajo/', views.OrdenTrabajoView.as_view(), name='orden_trabajo'),
    path('orden-trabajo/guardar/', views.OrdenTrabajoGuardarView.as_view(), name='orden_trabajo_guardar'),
    path('orden-trabajo/estado/', views.OrdenTrabajoCambiarEstadoView.as_view(), name='orden_trabajo_estado'),
]"""

campos_urls = campos_urls.replace("    path('eventos/crear/', views.EventoCuadroCreateView.as_view(), name='evento_create'),\n]", new_urls)

with open('apps/campos/urls.py', 'w', encoding='utf-8') as f:
    f.write(campos_urls)
    
print("URLs moved successfully!")
