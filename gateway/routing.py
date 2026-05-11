from django.conf import settings

# Maps URL prefix segment (after /api/v1/) to the SERVICE_URLS key.
# Order matters: more specific prefixes should come first if any overlap.
_PREFIX_TO_SERVICE: dict[str, str] = {
    'appointments': 'appointments',
    'payments': 'payments',
    'notifications': 'notifications',
    'schedule': 'schedule',
    'facility-staff': 'facility-staff',
    'medical-records': 'medical-records',
    'audit-logs': 'audit-logs',
}


def resolve_upstream_url(prefix: str, path: str, query_string: str) -> str | None:
    """
    Build the full upstream URL for a proxied request.

    Returns None if no service is registered for the given prefix.
    """
    service_key = _PREFIX_TO_SERVICE.get(prefix)
    if not service_key:
        return None

    base_url = settings.SERVICE_URLS.get(service_key, '').rstrip('/')
    if not base_url:
        return None

    tail = path.lstrip('/')
    upstream = f'{base_url}/api/v1/{prefix}/{tail}'
    if query_string:
        upstream += f'?{query_string}'
    return upstream


def registered_prefixes() -> list[str]:
    return list(_PREFIX_TO_SERVICE.keys())
