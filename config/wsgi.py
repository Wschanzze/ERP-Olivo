import os
import sys
from pathlib import Path
from django.core.wsgi import get_wsgi_application

# Asegurar que el directorio raíz del proyecto esté en el path de Python en Vercel
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# Alias requerido/recomendado por Vercel Python Runtime
app = application
