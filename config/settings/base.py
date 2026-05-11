from pathlib import Path

import environ

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

environ.Env.read_env(BASE_DIR / '.env', overwrite=False)

SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'gateway',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'gateway.middleware.CorrelationIdMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

# API Gateway is stateless — no database required.
# Set DATABASE_URL in env if admin/audit features are added later.
DATABASES = {}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'gateway.authentication.CognitoJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # Gateway does not use Django's auth stack; set to None so DRF never tries
    # to import AnonymousUser (which pulls in django.contrib.auth/contenttypes).
    'UNAUTHENTICATED_USER': None,
    'EXCEPTION_HANDLER': 'gateway.exceptions.custom_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Medical System — API Gateway',
    'DESCRIPTION': (
        'Unified entry point for the distributed medical platform. '
        'Validates Cognito JWTs, enforces role-based access, and proxies '
        'requests to downstream microservices.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SECURITY': [{'BearerAuth': []}],
    'SCHEMA_PATH_PREFIX': '/api/v1',
}

# AWS Cognito
COGNITO_USER_POOL_ID = env('COGNITO_USER_POOL_ID')
COGNITO_APP_CLIENT_ID = env('COGNITO_APP_CLIENT_ID')
COGNITO_REGION = env('COGNITO_REGION', default='eu-central-1')
# Explicit JWKS URL; if empty the authentication class builds it from pool id + region.
COGNITO_JWKS_URL = env('COGNITO_JWKS_URL', default='')

# Downstream microservice base URLs
SERVICE_URLS = {
    'appointments': env('APPOINTMENT_SERVICE_URL', default='http://appointment-service:8001'),
    'payments': env('PAYMENT_SERVICE_URL', default='http://payment-service:8002'),
    'notifications': env('NOTIFICATION_SERVICE_URL', default='http://notification-service:8003'),
    'schedule': env('SCHEDULE_SERVICE_URL', default='http://schedule-service:8004'),
    'facility-staff': env('FACILITY_STAFF_SERVICE_URL', default='http://facility-staff-service:8005'),
    'medical-records': env('MEDICAL_RECORD_SERVICE_URL', default='http://medical-record-service:8006'),
    'audit-logs': env('AUDIT_LOGGING_SERVICE_URL', default='http://audit-logging-service:8007'),
}

# Seconds to wait for an upstream response before returning 504
PROXY_TIMEOUT = env.int('PROXY_TIMEOUT', default=30)

# JWKS are public keys that rarely change; cache them to avoid hitting Cognito on every request.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
