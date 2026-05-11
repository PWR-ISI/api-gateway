from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default exception handler to produce the project-standard error shape:

        {
            "error": "ERROR_CODE",
            "detail": "Human-readable message",
            "fields": { "field_name": ["error"] }   // only for validation errors
        }
    """
    response = exception_handler(exc, context)
    if response is None:
        return None

    error_code = _derive_error_code(exc)
    detail = exc.detail if hasattr(exc, 'detail') else str(exc)

    if isinstance(detail, dict):
        # Validation error with per-field messages
        response.data = {
            'error': error_code,
            'detail': 'Validation failed.',
            'fields': detail,
        }
    elif isinstance(detail, list):
        response.data = {
            'error': error_code,
            'detail': ' '.join(str(d) for d in detail),
        }
    else:
        response.data = {
            'error': error_code,
            'detail': str(detail),
        }

    return response


def _derive_error_code(exc) -> str:
    name = type(exc).__name__
    # Convert CamelCase to UPPER_SNAKE: e.g. AuthenticationFailed → AUTHENTICATION_FAILED
    import re
    snake = re.sub(r'(?<!^)(?=[A-Z])', '_', name).upper()
    return snake
