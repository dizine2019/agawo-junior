import os
import dj_database_url
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =========================
# SECURITY
# =========================
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    default='django-insecure-17(a6ca#w@wrvm0536ll=4^=uhpbvc8t)e^^)=-kk*ywt__ju+'
)

# DEBUG: False in production (Render), True in development
DEBUG = 'False' not in os.environ

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".onrender.com"
]

# Tell Django it is running behind Render's secure reverse proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Accept and send session/CSRF cookies over HTTPS proxies securely
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Trust your Render domain subdomains for form submissions
CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com"
]

# =========================
# APPS
# =========================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Your Apps
    'core',
    
    # Third-party Apps
    'import_export',
]

# =========================
# MIDDLEWARE
# =========================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For efficient static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'agawo_junior.urls'

# =========================
# TEMPLATES (CRITICAL FIX FOR TemplateDoesNotExist)
# =========================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Looks for root /templates folder
        'APP_DIRS': True,                 # Looks in core/templates folder
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

WSGI_APPLICATION = 'agawo_junior.wsgi.application'

# =========================
# DATABASE
# =========================
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600
    )
}

# =========================
# PASSWORD VALIDATION
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =========================
# INTERNATIONALIZATION
# =========================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# =========================
# STATIC FILES
# =========================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Using WhiteNoise to serve static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# =========================
# LOGIN SETTINGS
# =========================
LOGIN_REDIRECT_URL = '/dashboard/'
LOGIN_URL = '/login/'

# =========================
# DEFAULT PRIMARY KEY
# =========================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
