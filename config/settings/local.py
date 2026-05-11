from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ['*']

SECRET_KEY = env('SECRET_KEY', default='django-insecure-local-dev-key-do-not-use-in-production')

# LocalStack emulates AWS services locally
AWS_ENDPOINT_URL = env('AWS_ENDPOINT_URL', default='http://localhost:4566')

COGNITO_USER_POOL_ID = env('COGNITO_USER_POOL_ID', default='eu-central-1_localpool')
COGNITO_APP_CLIENT_ID = env('COGNITO_APP_CLIENT_ID', default='local-client-id')
COGNITO_REGION = env('COGNITO_REGION', default='eu-central-1')

# When running with LocalStack, override the JWKS URL to point at the local endpoint.
# Leave blank to auto-build from pool id + region.
COGNITO_JWKS_URL = env(
    'COGNITO_JWKS_URL',
    default='',
)

# Override service URLs to reach sibling containers or local processes
SERVICE_URLS = {
    'appointments': env('APPOINTMENT_SERVICE_URL', default='http://localhost:8001'),
    'payments': env('PAYMENT_SERVICE_URL', default='http://localhost:8002'),
    'notifications': env('NOTIFICATION_SERVICE_URL', default='http://localhost:8003'),
    'schedule': env('SCHEDULE_SERVICE_URL', default='http://localhost:8004'),
    'facility-staff': env('FACILITY_STAFF_SERVICE_URL', default='http://localhost:8005'),
    'medical-records': env('MEDICAL_RECORD_SERVICE_URL', default='http://localhost:8006'),
    'audit-logs': env('AUDIT_LOGGING_SERVICE_URL', default='http://localhost:8007'),
}
