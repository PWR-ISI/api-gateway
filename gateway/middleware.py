import uuid


class CorrelationIdMiddleware:
    """
    Attaches a correlation ID to every request and echoes it back in the response.

    Reads X-Correlation-Id from the incoming request if present; otherwise generates
    a new UUID4. Downstream services receive the ID via the proxy header forwarding
    in ProxyView._build_upstream_headers().
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        correlation_id = request.META.get('HTTP_X_CORRELATION_ID') or str(uuid.uuid4())
        request.correlation_id = correlation_id

        response = self.get_response(request)
        response['X-Correlation-Id'] = correlation_id
        return response
