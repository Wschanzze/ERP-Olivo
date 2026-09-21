import os
import shutil
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Detectar si estamos en el entorno serverless de Vercel
IS_VERCEL = 'VERCEL' in os.environ

# Cargar variables de entorno desde .env
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', '').strip() or 'django-insecure-erp-olivo-fallback-key-2025-x98vercel'
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

# Soporte para proxies reversos (Vercel)
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Permitir todos los hosts en Vercel (incluyendo previews y dominios personalizados)
ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    'https://*.vercel.app',
    'https://*.now.sh',
    'http://localhost:*',
    'http://127.0.0.1:*',
]
csrf_env = os.getenv('CSRF_TRUSTED_ORIGINS')
if csrf_env:
    for origin in csrf_env.split(','):
        origin = origin.strip()
        if origin and origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Paquetes de terceros
    'rest_framework',
    'django_filters',
    'guardian',
    'corsheaders',

    # Apps del ERP Olivícola
    'apps.core',
    'apps.campos',
    'apps.inventario',
    'apps.parte_diario',
    'apps.costos',
    'apps.personal',
    'apps.liquidacion',
    'apps.finanzas',
    'apps.dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.erp_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Configuración de Base de Datos
DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')
USE_SQLITE = os.getenv('USE_SQLITE', 'False').lower() in ('true', '1')

if DATABASE_URL:
    is_pgbouncer = '6543' in DATABASE_URL or 'pgbouncer=true' in DATABASE_URL.lower()
    db_config = dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=0 if is_pgbouncer else 600,
        conn_health_checks=True,
        ssl_require=True,
    )
    # dj_database_url incluye parámetros query como opciones de conexión,
    # pero psycopg rechaza 'pgbouncer' como opción válida de conexión.
    if 'OPTIONS' in db_config and isinstance(db_config['OPTIONS'], dict):
        db_config['OPTIONS'].pop('pgbouncer', None)
    if is_pgbouncer:
        db_config['DISABLE_SERVER_SIDE_CURSORS'] = True
    DATABASES = {
        'default': db_config
    }
elif USE_SQLITE or (IS_VERCEL and not os.getenv('DB_HOST')):
    if IS_VERCEL:
        # En Vercel Serverless Functions, la raíz es de solo lectura. Sólo /tmp es escribible.
        sqlite_path = Path('/tmp') / 'db.sqlite3'
        seed_db = BASE_DIR / 'db_seed.sqlite3'
        if not seed_db.exists():
            seed_db = BASE_DIR / 'db.sqlite3'
        if seed_db.exists():
            try:
                if not sqlite_path.exists() or sqlite_path.stat().st_size == 0:
                    shutil.copyfile(seed_db, sqlite_path)
                try:
                    os.chmod(sqlite_path, 0o666)
                except Exception:
                    pass
            except Exception as e:
                print(f"Aviso al inicializar db en /tmp: {e}")
    else:
        sqlite_path = BASE_DIR / 'db.sqlite3'

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_path,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
            'NAME': os.getenv('DB_NAME', 'erp_olivo_db'),
            'USER': os.getenv('DB_USER', 'erp_user'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'erp_password_secret'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }

# Sistema de Caché en Memoria RAM (Ultra rápido para tablas de consulta frecuente como TipoCambio y Plan de Cuentas)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'erp-olivo-memory-cache',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000
        }
    }
}

# Modelo de Usuario personalizado y Backend de Permisos de Guardian
AUTH_USER_MODEL = 'core.Usuario'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

# Validadores de Contraseña
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internacionalización
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# Archivos Estáticos y Media
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
if (BASE_DIR / 'Public').exists():
    STATICFILES_DIRS.append(BASE_DIR / 'Public')

STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
WHITENOISE_MANIFEST_STRICT = False

MEDIA_URL = '/media/'
if IS_VERCEL:
    MEDIA_ROOT = Path('/tmp') / 'media'
else:
    MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
}

# CORS
CORS_ALLOW_ALL_ORIGINS = DEBUG

# Celery & Redis
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
