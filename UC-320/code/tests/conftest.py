"""Fixtures compartidas para tests de integración API de UC-320."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Token mock de HF con rol admin (para tests que necesitan todos los permisos)
TEST_HF_TOKEN = "hf_mock_token_admin"


class AuthenticatedClient:
    """Wrapper del Flask test client que inyecta headers de auth automáticamente."""

    def __init__(self, flask_client, hf_token=None):
        self._client = flask_client
        self._headers = {}
        if hf_token:
            self._headers["Authorization"] = f"Bearer {hf_token}"

    def _merge_headers(self, kwargs):
        headers = dict(self._headers)
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
        kwargs["headers"] = headers
        return kwargs

    def get(self, path, **kwargs):
        return self._client.get(path, **self._merge_headers(kwargs))

    def post(self, path, **kwargs):
        return self._client.post(path, **self._merge_headers(kwargs))

    def put(self, path, **kwargs):
        return self._client.put(path, **self._merge_headers(kwargs))

    def delete(self, path, **kwargs):
        return self._client.delete(path, **self._merge_headers(kwargs))

    def patch(self, path, **kwargs):
        return self._client.patch(path, **self._merge_headers(kwargs))

    @property
    def config(self):
        return self._client.application.config


@pytest.fixture
def client():
    """Cliente de test con token HF admin inyectado en todos los requests."""
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield AuthenticatedClient(c, TEST_HF_TOKEN)


@pytest.fixture
def viewer_client():
    """Cliente con rol viewer (permisos limitados)."""
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield AuthenticatedClient(c, "hf_mock_token_viewer")


@pytest.fixture
def user_client():
    """Cliente con rol user."""
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield AuthenticatedClient(c, "hf_mock_token_user")


@pytest.fixture
def developer_client():
    """Cliente con rol developer."""
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield AuthenticatedClient(c, "hf_mock_token_developer")


@pytest.fixture
def no_auth_client():
    """Cliente sin token (para tests de unauthorized)."""
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield AuthenticatedClient(c, None)
