import os
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if it exists
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

# Helper functions to replace django-environ functionality
def get_env(key, default=None):
    return os.environ.get(key, default)

def get_env_bool(key, default=False):
    value = os.environ.get(key, '')
    if value.lower() in ('true', '1', 'yes', 'on'):
        return True
    elif value.lower() in ('false', '0', 'no', 'off'):
        return False
    return default

def get_env_int(key, default=0):
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default

def get_env_list(key, default=None):
    if default is None:
        default = []
    value = os.environ.get(key, '')
    if value:
        return [item.strip() for item in value.split(',')]
    return default

# Security settings
SECRET_KEY = get_env('SECRET_KEY', 'django-insecure-change-in-production')
DEBUG = get_env_bool('DEBUG', True)
ALLOWED_HOSTS = get_env_list('ALLOWED_HOSTS', ['localhost', '127.0.0.1', '0.0.0.0'])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'safedelete',
    'encrypted_model_fields',
    'auditlog',
    'phonenumber_field',
    'django_countries',
    
    # Local apps
    'apps.users',
    'apps.organizations',
    'apps.contracts',
    'apps.charts',
    'apps.llm',
    'apps.billing',
    'apps.admin_console',
    
    'drf_yasg',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': get_env('DB_NAME', 'docbiz_db'),
        'USER': get_env('DB_USER', 'docbiz_user'),
        'PASSWORD': get_env('DB_PASSWORD', 'docbiz123'),
        'HOST': get_env('DB_HOST', 'localhost'),
        'PORT': get_env('DB_PORT', '5432'),
        'CONN_MAX_AGE': get_env_int('DB_CONN_MAX_AGE', 0),
        'OPTIONS': {
            'sslmode': get_env('DB_SSL_MODE', 'prefer'),
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'users.User'

# Django REST Framework
# config/settings.py

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/hour',
    },
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema',  # For drf-yasg
}

# drf-yasg Configuration
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': '''
            JWT Authentication. 
            Example: "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
            '''
        }
    },
    'USE_SESSION_AUTH': False,  # Set to True if you also use session auth
    'JSON_EDITOR': True,  # Enable JSON editor
    'DEEP_LINKING': True,  # Enable deep linking for tags and operations
    'PERSIST_AUTHORIZATION': True,  # Persist authorization when browser is closed
    'REFETCH_SCHEMA_ON_LOGOUT': True,  # Refetch schema after logout
    'VALIDATOR_URL': None,  # Disable schema validator (can be slow)
    
    # UI Customization
    'DOC_EXPANSION': 'none',  # ['none', 'list', 'full']
    'FILTER': True,  # Enable filter box
    'SHOW_REQUEST_HEADERS': True,
    'OPERATIONS_SORTER': 'alpha',  # ['alpha', 'method']
    'TAGS_SORTER': 'alpha',
    'DEFAULT_MODEL_RENDERING': 'example',  # ['example', 'model']
    'DEFAULT_MODEL_DEPTH': 2,
    
    # For JWT support
    'APIS_SORTER': 'alpha',
    'SUPPORTED_SUBMIT_METHODS': ['get', 'post', 'put', 'delete', 'patch'],
}

# Optional: Redoc settings
REDOC_SETTINGS = {
    'LAZY_RENDERING': True,
    'HIDE_HOSTNAME': False,
    'EXPAND_RESPONSES': ['200', '201'],
    'PATH_IN_MIDDLE': True,
    'NATIVE_SCROLLBARS': False,
    'REQUIRED_PROPS_FIRST': True,
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CORS
CORS_ALLOWED_ORIGINS = get_env_list('CORS_ALLOWED_ORIGINS', [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
])
CORS_ALLOW_CREDENTIALS = True

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Field Encryption
FIELD_ENCRYPTION_KEY = get_env('FIELD_ENCRYPTION_KEY', 'your-32-char-encryption-key-here')

# Email
EMAIL_BACKEND = get_env('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = get_env('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = get_env_int('EMAIL_PORT', 587)
EMAIL_USE_TLS = get_env_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = get_env('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = get_env('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = get_env('DEFAULT_FROM_EMAIL', 'DocBiz <noreply@docbiz.com>')

# LLM Configuration
OPENAI_API_KEY = get_env('OPENAI_API_KEY', '')
ANTHROPIC_API_KEY = get_env('ANTHROPIC_API_KEY', '')
GEMINI_API_KEY = get_env('GEMINI_API_KEY', '')
LLM_DEFAULT_PROVIDER = get_env('LLM_DEFAULT_PROVIDER', 'gemini')
LLM_DEFAULT_MODEL = get_env('LLM_DEFAULT_MODEL', 'gemini-pro')

# Audit Log
AUDITLOG_INCLUDE_ALL_MODELS = False

# Phone Number
PHONENUMBER_DEFAULT_REGION = 'US'

SPECTACULAR_SETTINGS = {
    'TITLE': 'DocBiz API',
    'DESCRIPTION': 'Document Business Intelligence Platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
