"""
Unit tests for ProxyView and HealthView.

Uses `responses` to mock upstream HTTP calls so no real services need to be running.
Cognito JWT authentication is monkeypatched — auth is tested separately.
No database required; @pytest.mark.django_db is intentionally omitted.
"""
import json

import pytest
import requests
import responses as resp_mock
from rest_framework.test import APIClient

from gateway.authentication import CognitoUser


def _make_user(role='PATIENT') -> CognitoUser:
    return CognitoUser({'sub': 'test-user-id', 'custom:role': role, 'email': 'test@example.com'})


@pytest.fixture()
def client():
    return APIClient()


@pytest.fixture(autouse=True)
def patch_auth(monkeypatch):
    """Bypass JWT validation for all view tests in this module."""
    from gateway import authentication
    monkeypatch.setattr(
        authentication.CognitoJWTAuthentication,
        'authenticate',
        lambda self, request: (_make_user(), 'fake-token'),
    )


class TestHealthView:
    def test_health_returns_200(self, client):
        response = client.get('/health/')
        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}

    def test_health_requires_no_auth(self, client, monkeypatch):
        from gateway import authentication
        monkeypatch.setattr(
            authentication.CognitoJWTAuthentication,
            'authenticate',
            lambda self, request: None,
        )
        response = client.get('/health/')
        assert response.status_code == 200


class TestProxyView:
    @resp_mock.activate
    def test_proxy_forwards_get_to_upstream(self, client, settings):
        settings.SERVICE_URLS = {'appointments': 'http://appointment-svc'}
        resp_mock.add(
            resp_mock.GET,
            'http://appointment-svc/api/v1/appointments/',
            json={'results': []},
            status=200,
        )

        response = client.get('/api/v1/appointments/')
        assert response.status_code == 200
        assert response.json() == {'results': []}

    @resp_mock.activate
    def test_proxy_forwards_post_body(self, client, settings):
        settings.SERVICE_URLS = {'appointments': 'http://appointment-svc'}
        resp_mock.add(
            resp_mock.POST,
            'http://appointment-svc/api/v1/appointments/',
            json={'id': 'new-appt'},
            status=201,
        )

        response = client.post(
            '/api/v1/appointments/',
            data=json.dumps({'doctor_id': 'doc-1'}),
            content_type='application/json',
        )
        assert response.status_code == 201

    @resp_mock.activate
    def test_proxy_returns_502_on_connection_error(self, client, settings):
        settings.SERVICE_URLS = {'appointments': 'http://appointment-svc'}
        # Must use requests.ConnectionError so the exception propagates through
        # the requests adapters correctly and our except clause catches it.
        resp_mock.add(
            resp_mock.GET,
            'http://appointment-svc/api/v1/appointments/',
            body=requests.ConnectionError('simulated connection error'),
        )

        response = client.get('/api/v1/appointments/')
        assert response.status_code == 502
        assert response.json()['error'] == 'SERVICE_UNAVAILABLE'

    def test_proxy_returns_404_for_unknown_prefix(self, client, settings):
        settings.SERVICE_URLS = {}
        response = client.get('/api/v1/unknown-service/')
        assert response.status_code == 404
        assert response.json()['error'] == 'SERVICE_NOT_FOUND'

    @resp_mock.activate
    def test_proxy_injects_user_identity_headers(self, client, settings):
        settings.SERVICE_URLS = {'appointments': 'http://appointment-svc'}
        resp_mock.add(
            resp_mock.GET,
            'http://appointment-svc/api/v1/appointments/',
            json={'results': []},
            status=200,
        )

        client.get('/api/v1/appointments/')

        sent_headers = resp_mock.calls[0].request.headers
        # requests uses CaseInsensitiveDict so key case does not matter
        assert sent_headers.get('x-user-id') == 'test-user-id'
        assert sent_headers.get('x-user-role') == 'PATIENT'

    @resp_mock.activate
    def test_proxy_propagates_upstream_status_codes(self, client, settings):
        settings.SERVICE_URLS = {'appointments': 'http://appointment-svc'}
        resp_mock.add(
            resp_mock.GET,
            'http://appointment-svc/api/v1/appointments/missing/',
            json={'error': 'NOT_FOUND', 'detail': 'Appointment not found.'},
            status=404,
        )

        response = client.get('/api/v1/appointments/missing/')
        assert response.status_code == 404
        assert response.json()['error'] == 'NOT_FOUND'
