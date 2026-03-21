"""
Django settings for ERP project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv



load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-this-in-production')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',  # For intcomma filter
    'rest_framework',
    'corsheaders',
    # Temporarily disabled Bloomerp due to langgraph compatibility issue
    # 'django_htmx',  # Required for Bloomerp
    # 'bloomerp',  # Bloomerp Framework - TODO: Re-enable after framework update
    'core',
    'projects',
    'resources',
    'budgeting',
    'clients',
    'performance',
    'ai',
    'accounting',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 'core.middleware.AutoLoginMiddleware',  # Dev/Test only: bỏ comment để auto-login superuser
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Temporarily disabled HTMX middleware for Bloomerp
    # 'django_htmx.middleware.HtmxMiddleware',  # HTMX middleware for Bloomerp
]

ROOT_URLCONF = 'ERP.urls'

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
                'core.context_processors.user_profile',
            ],
        },
    },
]

# Admin site configuration
ADMIN_SITE_HEADER = "Hệ thống ERP - Trang quản trị"
ADMIN_SITE_TITLE = "ERP Admin"
ADMIN_INDEX_TITLE = "Chào mừng đến với trang quản trị ERP"

WSGI_APPLICATION = 'ERP.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': os.getenv('DB_NAME', 'ERP_DB'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            'trusted_connection': 'yes' if os.getenv('DB_TRUSTED_CONNECTION', 'true').lower() == 'true' else 'no',
        },
    }
}

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

LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

# Number formatting (used by templates: intcomma/floatformat)
# Ensure thousand separators show as comma, e.g. 500,000,000
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = ','
NUMBER_GROUPING = 3

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Email configuration (OTP, notifications)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_SERVICE = os.getenv('EMAIL_SERVICE', 'gmail')

if EMAIL_SERVICE == 'gmail':
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
else:
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'

EMAIL_HOST_USER = os.getenv('EMAIL_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or os.getenv('ADMIN_EMAIL', 'admin@example.com')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', DEFAULT_FROM_EMAIL)

# Bloomerp Framework Configuration
BLOOMERP_SETTINGS = {
    "globals": {
        "organization_name": "ERP System",
    },
    "BASE_URL": "",
    "ROUTERS": [
        'projects.bloomerp_router.router',  # Project management router
        'resources.bloomerp_router.router',  # Resource management router
        'budgeting.bloomerp_router.router',  # Budgeting router
        'clients.bloomerp_router.router',  # Clients router
    ],
    "OPENAI_API_KEY": os.getenv('OPENAI_API_KEY', ''),  # Optional: for LLM integration
    "LOGIN_URL": "login",  # Set login URL as recommended
    "AUTO_LINK_GENERATOR": False,  # Disable auto link generator in production
}
