import logging

import requests as http_requests
from django.conf import settings
from django.core.cache import cache
from jose import JWTError, jwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)

_JWKS_CACHE_KEY = 'cognito_jwks'
_JWKS_CACHE_TTL = 3600  # 1 hour — Cognito rotates keys infrequently


class CognitoUser:
    """Lightweight principal populated from a verified Cognito JWT payload."""

    is_authenticated = True

    def __init__(self, payload: dict) -> None:
        self.user_id: str = payload['sub']
        self.role: str = payload.get('custom:role', 'PATIENT')
        self.email: str = payload.get('email', '')
        self.username: str = payload.get('cognito:username', self.user_id)
        self._payload = payload

    def __str__(self) -> str:
        return f'CognitoUser(id={self.user_id}, role={self.role})'


class CognitoJWTAuthentication(BaseAuthentication):
    """
    Validates RS256 JWTs issued by AWS Cognito.

    On success returns (CognitoUser, raw_token).
    Returns None if no Authorization header is present (allows public endpoints).
    Raises AuthenticationFailed for malformed or expired tokens.
    """

    def authenticate(self, request):
        token = self._extract_bearer_token(request)
        if not token:
            return None

        try:
            payload = self._verify_token(token)
        except AuthenticationFailed:
            raise
        except Exception as exc:
            logger.exception('Unexpected error during JWT authentication')
            raise AuthenticationFailed('Authentication failed.') from exc

        return (CognitoUser(payload), token)

    def authenticate_header(self, request) -> str:
        return 'Bearer realm="medical-system"'

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_bearer_token(self, request) -> str | None:
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None
        token = auth_header[7:].strip()
        return token or None

    def _verify_token(self, token: str) -> dict:
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise AuthenticationFailed(f'Malformed token header: {exc}') from exc

        jwks = self._get_jwks()
        signing_key = next(
            (k for k in jwks.get('keys', []) if k.get('kid') == unverified_header.get('kid')),
            None,
        )
        if not signing_key:
            # The key may have been rotated — bust the cache and retry once
            cache.delete(_JWKS_CACHE_KEY)
            jwks = self._get_jwks()
            signing_key = next(
                (k for k in jwks.get('keys', []) if k.get('kid') == unverified_header.get('kid')),
                None,
            )
        if not signing_key:
            raise AuthenticationFailed('Signing key not found in JWKS.')

        try:
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=['RS256'],
                audience=settings.COGNITO_APP_CLIENT_ID,
                options={'verify_exp': True, 'verify_aud': True},
            )
        except JWTError as exc:
            raise AuthenticationFailed(f'Token validation failed: {exc}') from exc

        return payload

    def _get_jwks(self) -> dict:
        cached = cache.get(_JWKS_CACHE_KEY)
        if cached:
            return cached

        jwks_url = settings.COGNITO_JWKS_URL or self._build_jwks_url()
        try:
            response = http_requests.get(jwks_url, timeout=5)
            response.raise_for_status()
            jwks = response.json()
        except Exception as exc:
            logger.error('Failed to fetch JWKS from %s: %s', jwks_url, exc)
            raise AuthenticationFailed('Cannot retrieve authentication keys.') from exc

        cache.set(_JWKS_CACHE_KEY, jwks, _JWKS_CACHE_TTL)
        return jwks

    def _build_jwks_url(self) -> str:
        return (
            f'https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com/'
            f'{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json'
        )
