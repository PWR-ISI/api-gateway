"""Unit tests for the routing helper."""
import pytest

from gateway.routing import resolve_upstream_url, registered_prefixes

_SERVICE_URLS = {
    'appointments': 'http://appt-svc:8001',
    'payments': 'http://pay-svc:8002',
}


@pytest.fixture(autouse=True)
def set_service_urls(settings):
    settings.SERVICE_URLS = _SERVICE_URLS


class TestResolveUpstreamUrl:
    def test_known_prefix_no_path(self):
        url = resolve_upstream_url('appointments', '', '')
        assert url == 'http://appt-svc:8001/api/v1/appointments/'

    def test_known_prefix_with_path(self):
        url = resolve_upstream_url('appointments', 'abc-123/', '')
        assert url == 'http://appt-svc:8001/api/v1/appointments/abc-123/'

    def test_known_prefix_with_query_string(self):
        url = resolve_upstream_url('appointments', '', 'date=2026-05-01')
        assert url == 'http://appt-svc:8001/api/v1/appointments/?date=2026-05-01'

    def test_unknown_prefix_returns_none(self):
        assert resolve_upstream_url('nonexistent', '', '') is None

    def test_registered_prefixes_returns_list(self):
        prefixes = registered_prefixes()
        assert 'appointments' in prefixes
        assert 'payments' in prefixes
