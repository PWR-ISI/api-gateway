import logging

import requests as http_requests
from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import CognitoJWTAuthentication
from .routing import resolve_upstream_url

logger = logging.getLogger(__name__)

# Headers that must not be forwarded to upstream services (hop-by-hop).
_HOP_BY_HOP = frozenset({
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailers', 'transfer-encoding', 'upgrade', 'host',
})

# Headers that must not be copied from the upstream response back to the client.
_DROP_FROM_UPSTREAM = frozenset({
    'content-encoding', 'content-length', 'transfer-encoding', 'connection',
})


class HealthView(APIView):
    """Liveness probe — no auth, no database. Required by ECS/ALB health checks."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'status': 'ok'})


class ProxyView(APIView):
    """
    Reverse proxy for all /api/v1/<prefix>/<path> requests.

    Validates the Cognito JWT, injects X-User-Id / X-User-Role headers, then
    forwards the request verbatim to the appropriate downstream service.
    """

    authentication_classes = [CognitoJWTAuthentication]
    # Permission enforcement happens per-service downstream; the gateway only
    # requires a valid JWT (IsAuthenticated via DEFAULT_PERMISSION_CLASSES).

    def dispatch(self, request, *args, **kwargs):
        # DRF's dispatch() calls authenticate() before calling the HTTP method handler.
        # We override dispatch entirely so a single method handles every HTTP verb.
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, prefix, path=''):
        return self._proxy(request, prefix, path)

    def post(self, request, prefix, path=''):
        return self._proxy(request, prefix, path)

    def put(self, request, prefix, path=''):
        return self._proxy(request, prefix, path)

    def patch(self, request, prefix, path=''):
        return self._proxy(request, prefix, path)

    def delete(self, request, prefix, path=''):
        return self._proxy(request, prefix, path)

    def head(self, request, prefix, path=''):
        return self._proxy(request, prefix, path)

    def options(self, request, prefix, path=''):
        return self._proxy(request, prefix, path)

    # ------------------------------------------------------------------
    # Core proxy logic
    # ------------------------------------------------------------------

    def _proxy(self, request, prefix: str, path: str) -> Response:
        query_string = request.META.get('QUERY_STRING', '')
        upstream_url = resolve_upstream_url(prefix, path, query_string)

        if upstream_url is None:
            return Response(
                {'error': 'SERVICE_NOT_FOUND', 'detail': f'No service registered for prefix "/{prefix}/".'},
                status=404,
            )

        headers = self._build_upstream_headers(request)

        try:
            upstream_resp = http_requests.request(
                method=request.method,
                url=upstream_url,
                headers=headers,
                data=request.body,
                timeout=getattr(settings, 'PROXY_TIMEOUT', 30),
                allow_redirects=False,
                stream=False,
            )
        except http_requests.Timeout:
            logger.error('Upstream timeout: %s %s', request.method, upstream_url)
            return Response(
                {'error': 'UPSTREAM_TIMEOUT', 'detail': 'The upstream service did not respond in time.'},
                status=504,
            )
        except http_requests.ConnectionError as exc:
            logger.error('Upstream connection error: %s %s — %s', request.method, upstream_url, exc)
            return Response(
                {'error': 'SERVICE_UNAVAILABLE', 'detail': 'The upstream service is unavailable.'},
                status=502,
            )

        return self._build_response(upstream_resp)

    def _build_upstream_headers(self, request) -> dict:
        headers: dict[str, str] = {}

        for meta_key, value in request.META.items():
            if meta_key.startswith('HTTP_'):
                header = meta_key[5:].replace('_', '-').lower()
                if header not in _HOP_BY_HOP:
                    headers[header] = value
            elif meta_key == 'CONTENT_TYPE' and value:
                headers['content-type'] = value
            elif meta_key == 'CONTENT_LENGTH' and value:
                headers['content-length'] = value

        # Inject verified identity so downstream services can trust it without re-validating the JWT
        user = getattr(request, 'user', None)
        if user and hasattr(user, 'user_id'):
            headers['x-user-id'] = user.user_id or ''
            headers['x-user-role'] = user.role or ''

        if hasattr(request, 'correlation_id'):
            headers['x-correlation-id'] = request.correlation_id

        return headers

    def _build_response(self, upstream_resp: http_requests.Response) -> Response:
        try:
            data = upstream_resp.json()
        except ValueError:
            data = upstream_resp.text

        response = Response(data=data, status=upstream_resp.status_code)

        for header, value in upstream_resp.headers.items():
            if header.lower() not in _DROP_FROM_UPSTREAM:
                response[header] = value

        return response


class SchemaAggregateView(APIView):
    """
    Fetches OpenAPI schemas from all registered downstream services and merges
    them into a single document. Useful for generating a unified client SDK.

    Services that are unreachable are silently skipped (a warning is logged).
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request) -> Response:
        merged: dict = {
            'openapi': '3.0.3',
            'info': {'title': 'Medical System — Full API', 'version': '1.0.0'},
            'paths': {},
            'components': {
                'schemas': {},
                'securitySchemes': {
                    'BearerAuth': {
                        'type': 'http',
                        'scheme': 'bearer',
                        'bearerFormat': 'JWT',
                    }
                },
            },
            'security': [{'BearerAuth': []}],
        }

        service_urls: dict = getattr(settings, 'SERVICE_URLS', {})
        for service_key, base_url in service_urls.items():
            schema_url = f'{base_url.rstrip("/")}/api/schema/'
            try:
                resp = http_requests.get(schema_url, timeout=5)
                resp.raise_for_status()
                svc_schema = resp.json()
            except Exception as exc:
                logger.warning('Could not fetch schema for service "%s" from %s: %s', service_key, schema_url, exc)
                continue

            for path, definition in svc_schema.get('paths', {}).items():
                merged['paths'][path] = definition

            for name, component in svc_schema.get('components', {}).get('schemas', {}).items():
                merged['components']['schemas'][f'{service_key}__{name}'] = component

        return Response(merged)
