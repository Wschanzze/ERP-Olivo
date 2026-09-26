import os
import shutil
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Detectar si estamos en el entorno serverless de Vercel o en Railway
IS_VERCEL = 'VERCEL' in os.environ
IS_RAILWAY = 'RAILWAY_ENVIRONMENT' in os.environ or 'RAILWAY_PROJECT_ID' in os.environ or 'RAILWAY_SERVICE_ID' in os.environ

# Cargar variables de entorno desde .env
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', '').strip() or 'django-insecure-erp-olivo-fallback-key-2025-x98vercel'
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

# Soporte para proxies reversos (Vercel, Railway, Traefik, Nginx)
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Hosts permitidos
allowed_hosts_env = os.getenv('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(',') if host.strip()]


CSRF_TRUSTED_ORIGINS = [
    'https://*.vercel.app',
    'https://*.now.sh',
    'https://*.railway.app',
    'https://*.up.railway.app',
    'http://localhost:*',
    'http://127.0.0.1:*',
]

# Agregar automáticamente dominio asignado por Railway si existe
railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
if railway_domain:
    origin = f"https://{railway_domain}"
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

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
    'apps.core.middleware.ERPAuthMiddleware',
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
DATABASE_URL = (
    os.getenv('DATABASE_URL')
    or os.getenv('POSTGRES_URL')
    or os.getenv('DATABASE_PUBLIC_URL')
    or os.getenv('DATABASE_PRIVATE_URL')
)
USE_SQLITE = os.getenv('USE_SQLITE', 'False').lower() in ('true', '1')

# Variables estándar de PostgreSQL (compatibles con Railway, Docker Compose, etc.)
DB_HOST = os.getenv('DB_HOST') or os.getenv('PGHOST')
DB_PORT = os.getenv('DB_PORT') or os.getenv('PGPORT', '5432')
DB_NAME = os.getenv('DB_NAME') or os.getenv('PGDATABASE', 'erp_olivo_db')
DB_USER = os.getenv('DB_USER') or os.getenv('PGUSER', 'erp_user')
DB_PASSWORD = os.getenv('DB_PASSWORD') or os.getenv('PGPASSWORD', 'erp_password_secret')

if DATABASE_URL:
    is_pgbouncer = '6543' in DATABASE_URL or 'pgbouncer=true' in DATABASE_URL.lower()
    # Supabase o URLs con sslmode=require requieren SSL; en redes internas (Railway/Docker) no se fuerza si no se especifica
    ssl_required = (
        'supabase.co' in DATABASE_URL
        or 'sslmode=require' in DATABASE_URL.lower()
        or os.getenv('DB_SSL_REQUIRE', '').lower() in ('true', '1')
    )
    db_config = dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=0 if is_pgbouncer else 600,
        conn_health_checks=True,
        ssl_require=ssl_required,
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
elif DB_HOST and not USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
        }
    }
else:
    # Fallback a SQLite para desarrollo local, Vercel o Railway (sin Postgres aprovisionado)
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
        seed_db = BASE_DIR / 'db_seed.sqlite3'
        if not sqlite_path.exists() and seed_db.exists():
            try:
                shutil.copyfile(seed_db, sqlite_path)
            except Exception as e:
                print(f"Aviso al inicializar db.sqlite3 desde seed: {e}")

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_path,
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
WHITENOISE_USE_FINDERS = True

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
_redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL') or _redis_url
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND') or _redis_url
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# ──────────────────────────────────────────────────────────────────────────────
# ARCA (ex AFIP) - AfipSDK Configuration
# ──────────────────────────────────────────────────────────────────────────────
AFIP_ACCESS_TOKEN = os.getenv('AFIP_ACCESS_TOKEN', '').strip()
afip_cuit_env = os.getenv('AFIP_CUIT', '').strip()
AFIP_CUIT = int(afip_cuit_env) if afip_cuit_env.isdigit() else 0
AFIP_PRODUCTION = os.getenv('AFIP_PRODUCTION', 'False').lower() in ('true', '1')
AFIP_DEFAULT_PTO_VTA = int(os.getenv('AFIP_DEFAULT_PTO_VTA', '1'))
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', '').strip()

# ──────────────────────────────────────────────────────────────────────────────
# Supabase Auth & Cloud Configuration
# ──────────────────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv('SUPABASE_URL', '').strip()
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', '').strip()
SUPABASE_SECRET_KEY = os.getenv('SUPABASE_SECRET_KEY', '').strip()
SUPABASE_PUBLISHABLE_KEY = os.getenv('SUPABASE_PUBLISHABLE_KEY', '').strip()
SUPABASE_JWKS_URL = os.getenv('SUPABASE_JWKS_URL', '').strip()

# Rutas de Autenticación y Redirección
LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'dashboard:index'
LOGOUT_REDIRECT_URL = 'core:login'

# En entornos serverless sin workers dedicados, o si se fuerza localmente:
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False').lower() in ('true', '1') or IS_VERCEL
CELERY_TASK_STORE_EAGER_RESULT = CELERY_TASK_ALWAYS_EAGER
