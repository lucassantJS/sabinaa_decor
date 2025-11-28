import os
from pathlib import Path
from decouple import config, Csv
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- SEGURANÇA ---
SECRET_KEY = config('SECRET_KEY')

# Leitura correta do DEBUG (Pega do .env ou assume False)
DEBUG = config('DEBUG', default=False, cast=bool)

# ✅ CORREÇÃO CRÍTICA: ALLOWED_HOSTS para Railway
ALLOWED_HOSTS = [
    'web-production-5b90.up.railway.app',
    '.railway.app', 
    'localhost',
    '127.0.0.1'
]

# ✅ CORREÇÃO: CSRF para domínio específico
CSRF_TRUSTED_ORIGINS = [
    'https://web-production-5b90.up.railway.app',
    'https://*.railway.app'
]

# --- APLICAÇÃO ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'anymail',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Libs de terceiros
    'widget_tweaks',
    # Seus apps
    'app',
]

# --- LOGGING ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'app': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sabina_decor.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

WSGI_APPLICATION = 'sabina_decor.wsgi.application'

# --- BANCO DE DADOS ---
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
    )
}

# --- VALIDAÇÃO DE SENHA ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- INTERNACIONALIZAÇÃO ---
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# --- ARQUIVOS ESTÁTICOS (CSS/JS) ---
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# --- ARQUIVOS DE MÍDIA (Uploads) ---
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# --- CONFIGURAÇÕES DE LOGIN/LOGOUT ---
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/inicio/'
LOGOUT_REDIRECT_URL = '/inicio/'

# --- EMAIL (CONFIGURAÇÃO GMAIL - MODO SSL BLINDADO) ---
EMAIL_BACKEND = "anymail.backends.sendgrid.EmailBackend"

ANYMAIL = {
    "SENDGRID_API_KEY": config("SENDGRID_API_KEY"),
}

# Use o mesmo e-mail padrão que você já tinha
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# COMENTE ESTAS LINHAS ABAIXO PARA O E-MAIL SAIR DE VERDADE:
# if DEBUG:
#     EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
#     DEFAULT_FROM_EMAIL = 'Sabina Decorações <lucashenri0231@gmail.com>'