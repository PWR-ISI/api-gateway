"""
Unit tests for CognitoJWTAuthentication.

No database required — no @pytest.mark.django_db on these tests.
The full JWT crypto path is covered by unit-mocking _verify_token and _get_jwks.
"""
from unittest.mock import patch

import pytest
import responses as resp_mock
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from gateway.authentication import CognitoJWTAuthentication, CognitoUser


@pytest.fixture()
def auth():
    return CognitoJWTAuthentication()


@pytest.fixture()
def rf():
    return APIRequestFactory()


def _wrap(raw_request) -> Request:
    return Request(raw_request)


class TestTokenExtraction:
    def test_returns_none_when_no_header(self, auth, rf):
        assert auth.authenticate(_wrap(rf.get('/'))) is None

    def test_returns_none_for_non_bearer_scheme(self, auth, rf):
        request = _wrap(rf.get('/', HTTP_AUTHORIZATION='Basic dXNlcjpwYXNz'))
        assert auth.authenticate(request) is None

    def test_returns_none_for_empty_bearer_value(self, auth, rf):
        request = _wrap(rf.get('/', HTTP_AUTHORIZATION='Bearer '))
        assert auth.authenticate(request) is None


class TestTokenVerification:
    def test_valid_token_returns_cognito_user(self, auth, rf, monkeypatch):
        monkeypatch.setattr(
            CognitoJWTAuthentication,
            '_verify_token',
            lambda self, token: {
                'sub': 'user-uuid-123',
                'custom:role': 'PATIENT',
                'email': 'patient@example.com',
            },
        )
        request = _wrap(rf.get('/', HTTP_AUTHORIZATION='Bearer mock-valid-token'))
        user, token = auth.authenticate(request)

        assert isinstance(user, CognitoUser)
        assert user.user_id == 'user-uuid-123'
        assert user.role == 'PATIENT'
        assert user.email == 'patient@example.com'
        assert user.is_authenticated is True
        assert token == 'mock-valid-token'

    def test_malformed_jose_header_raises_authentication_failed(self, auth, rf):
        request = _wrap(rf.get('/', HTTP_AUTHORIZATION='Bearer not.valid'))
        with pytest.raises(AuthenticationFailed):
            auth.authenticate(request)

    def test_verify_token_raises_when_kid_not_in_jwks(self, auth, settings, monkeypatch):
        settings.COGNITO_JWKS_URL = 'https://fake-jwks.example.com/'
        settings.COGNITO_APP_CLIENT_ID = 'test-client'

        monkeypatch.setattr(
            CognitoJWTAuthentication,
            '_get_jwks',
            lambda self: {'keys': []},  # empty — no matching kid
        )
        # Create a minimally valid-looking JWT header (wrong kid)
        import base64, json
        header = base64.urlsafe_b64encode(json.dumps({'alg': 'RS256', 'kid': 'unknown-kid'}).encode()).rstrip(b'=')
        payload = base64.urlsafe_b64encode(b'{}').rstrip(b'=')
        fake_token = f'{header.decode()}.{payload.decode()}.fakesig'

        with pytest.raises(AuthenticationFailed, match='Signing key not found'):
            auth._verify_token(fake_token)


class TestJwksFetching:
    @resp_mock.activate
    def test_fetches_jwks_from_configured_url(self, auth, settings):
        settings.COGNITO_JWKS_URL = 'https://example.com/.well-known/jwks.json'
        jwks = {'keys': [{'kid': 'k1', 'kty': 'RSA'}]}
        resp_mock.add(resp_mock.GET, 'https://example.com/.well-known/jwks.json', json=jwks, status=200)

        with patch('gateway.authentication.cache.get', return_value=None), \
             patch('gateway.authentication.cache.set') as mock_set:
            result = auth._get_jwks()

        assert result == jwks
        mock_set.assert_called_once()

    @resp_mock.activate
    def test_builds_jwks_url_from_pool_id_and_region_when_not_set(self, auth, settings):
        settings.COGNITO_JWKS_URL = ''
        settings.COGNITO_USER_POOL_ID = 'eu-central-1_testpool'
        settings.COGNITO_REGION = 'eu-central-1'
        expected_url = 'https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_testpool/.well-known/jwks.json'

        resp_mock.add(resp_mock.GET, expected_url, json={'keys': []}, status=200)

        with patch('gateway.authentication.cache.get', return_value=None), \
             patch('gateway.authentication.cache.set'):
            auth._get_jwks()

        assert resp_mock.calls[0].request.url == expected_url

    @resp_mock.activate
    def test_raises_authentication_failed_when_jwks_endpoint_unavailable(self, auth, settings):
        settings.COGNITO_JWKS_URL = 'https://example.com/.well-known/jwks.json'
        resp_mock.add(resp_mock.GET, 'https://example.com/.well-known/jwks.json', status=500)

        with patch('gateway.authentication.cache.get', return_value=None):
            with pytest.raises(AuthenticationFailed, match='Cannot retrieve'):
                auth._get_jwks()

    def test_returns_cached_jwks_without_network_call(self, auth, settings):
        cached_jwks = {'keys': [{'kid': 'cached-k', 'kty': 'RSA'}]}
        with patch('gateway.authentication.cache.get', return_value=cached_jwks):
            result = auth._get_jwks()
        assert result == cached_jwks
