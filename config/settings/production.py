from .base import *  # noqa: F401, F403

DEBUG = False

AWS_ENDPOINT_URL = None  # Use real AWS SDK defaults

# Build standard Cognito JWKS URL from the pool ID and region injected via env.
COGNITO_JWKS_URL = (
    f'https://cognito-idp.{COGNITO_REGION}.amazonaws.com/'
    f'{COGNITO_USER_POOL_ID}/.well-known/jwks.json'
)

# Trust the ALB / reverse proxy for HTTPS detection
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)

# Use Redis cache in production for JWKS + shared state
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}
