"""Tests de AAA: Autenticación, Autorización y Acceso con Hugging Face."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Autenticación ---

def test_no_auth_rejected(no_auth_client):
    """Sin token HF → 401 unauthorized."""
    resp = no_auth_client.get("/api/v1/models")
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "unauthorized"


def test_invalid_token_rejected(client):
    """Token inválido → 401 unauthorized."""
    from api_320 import app
    with app.test_client() as c:
        resp = c.get("/api/v1/models", headers={"Authorization": "Bearer hf_invalid_token"})
        assert resp.status_code == 401


def test_auth_login_success(client):
    """Login con token mock admin → authenticated=True."""
    resp = client.post("/api/v1/auth/login")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["authenticated"]
    assert data["session"]["hf_username"] == "mock_admin"


def test_auth_login_with_body():
    """Login con token en el body."""
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        resp = c.post("/api/v1/auth/login", json={"hf_token": "hf_mock_token_user"})
        assert resp.status_code == 200
        assert resp.get_json()["session"]["hf_username"] == "mock_user"


def test_auth_login_no_token():
    """Login sin token → 401."""
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        resp = c.post("/api/v1/auth/login")
        assert resp.status_code == 401


def test_auth_whoami(client):
    """Whoami retorna identidad del usuario."""
    resp = client.get("/api/v1/auth/whoami")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "mock_admin"
    assert data["role"] == "admin"
    assert "permissions" in data


def test_auth_whoami_no_auth(no_auth_client):
    """Whoami sin auth → 401."""
    resp = no_auth_client.get("/api/v1/auth/whoami")
    assert resp.status_code == 401


def test_auth_logout(client):
    """Logout cierra la sesión."""
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.get_json()["logged_out"]


def test_auth_status_public():
    """Auth status es público (no requiere token)."""
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        resp = c.get("/api/v1/auth/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "auth_method" in data
        assert "billing" in data


def test_auth_sessions_admin_only(client):
    """Sessions list requiere admin."""
    resp = client.get("/api/v1/auth/sessions")
    assert resp.status_code == 200  # admin puede


def test_auth_sessions_forbidden_for_viewer(viewer_client):
    """Viewer no puede ver sessions."""
    resp = viewer_client.get("/api/v1/auth/sessions")
    assert resp.status_code == 403


# --- Autorización por rol ---

def test_viewer_can_read_models(viewer_client):
    """Viewer puede listar modelos."""
    resp = viewer_client.get("/api/v1/models")
    assert resp.status_code == 200


def test_viewer_cannot_create_endpoint(viewer_client):
    """Viewer no puede crear endpoints."""
    resp = viewer_client.post("/api/v1/endpoints", json={"name": "test", "model_id": "mock/sentiment-mock"})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_viewer_cannot_train(viewer_client):
    """Viewer no puede entrenar."""
    resp = viewer_client.post("/api/v1/trainer/train", json={
        "base_model": "mock/sentiment-mock", "dataset_id": "ds", "output_dir": "out", "objective": "test"
    })
    assert resp.status_code == 403


def test_user_can_infer(user_client):
    """User puede hacer inferencia."""
    resp = user_client.post("/api/v1/sentiment", json={
        "ticker": "AAPL", "article": "Apple beats earnings", "model_id": "mock/sentiment-mock"
    })
    assert resp.status_code == 200


def test_user_cannot_create_endpoint(user_client):
    """User no puede crear endpoints (requiere developer)."""
    resp = user_client.post("/api/v1/endpoints", json={"name": "test", "model_id": "mock/sentiment-mock"})
    assert resp.status_code == 403


def test_developer_can_create_endpoint(developer_client):
    """Developer puede crear endpoints."""
    resp = developer_client.post("/api/v1/endpoints", json={"name": "dev-ep", "model_id": "mock/sentiment-mock"})
    assert resp.status_code == 200


def test_developer_can_train(developer_client):
    """Developer puede entrenar."""
    resp = developer_client.post("/api/v1/trainer/train", json={
        "base_model": "mock/sentiment-mock", "dataset_id": "ds", "output_dir": "out", "objective": "test"
    })
    assert resp.status_code == 200


def test_developer_cannot_delete_endpoint(developer_client):
    """Developer no puede eliminar endpoints (requiere admin)."""
    # Crear primero
    create = developer_client.post("/api/v1/endpoints", json={"name": "dev-ep2", "model_id": "mock/sentiment-mock"})
    eid = create.get_json()["endpoint"]["endpoint_id"]
    resp = developer_client.delete(f"/api/v1/endpoints/{eid}")
    assert resp.status_code == 403


def test_admin_can_delete_endpoint(client):
    """Admin puede eliminar endpoints."""
    create = client.post("/api/v1/endpoints", json={"name": "admin-ep", "model_id": "mock/sentiment-mock"})
    eid = create.get_json()["endpoint"]["endpoint_id"]
    resp = client.delete(f"/api/v1/endpoints/{eid}")
    assert resp.status_code == 200


def test_admin_can_promote(client):
    """Admin puede promover modelos."""
    # Submit + run training
    submit = client.post("/api/v1/training/submit", json={
        "base_model": "mock/sentiment-mock", "dataset_id": "ds",
        "dataset_revision": "v1", "objective": "test"
    })
    job_id = submit.get_json()["job_id"]
    client.post("/api/v1/training/run", json={"job_id": job_id})
    resp = client.post("/api/v1/training/promote", json={"job_id": job_id, "human_approved": True})
    assert resp.status_code == 200


def test_developer_cannot_promote(developer_client):
    """Developer no puede promover (requiere admin)."""
    resp = developer_client.post("/api/v1/training/promote", json={"job_id": "fake", "human_approved": True})
    assert resp.status_code == 403


# --- Acceso: billing al usuario ---

def test_sentiment_billing_info(client):
    """La respuesta de sentiment incluye info de billing."""
    resp = client.post("/api/v1/sentiment", json={
        "ticker": "AAPL", "article": "Apple beats earnings", "model_id": "mock/sentiment-mock"
    })
    data = resp.get_json()
    assert "billing" in data
    assert data["billing"]["charged_to"] == "mock_admin"


def test_endpoint_billing_info(client):
    """Crear endpoint incluye billing al usuario."""
    resp = client.post("/api/v1/endpoints", json={"name": "billing-test", "model_id": "mock/sentiment-mock"})
    data = resp.get_json()
    assert "billing" in data
    assert data["billing"]["charged_to"] == "mock_admin"


def test_trainer_billing_info(client):
    """Entrenar incluye billing al usuario."""
    resp = client.post("/api/v1/trainer/train", json={
        "base_model": "mock/sentiment-mock", "dataset_id": "ds",
        "output_dir": "out", "objective": "test"
    })
    data = resp.get_json()
    # Con token de usuario, billing va al usuario
    if "billing" in data:
        assert data["billing"]["charged_to"] == "mock_admin"


def test_dataset_billing_info(client):
    """Cargar dataset incluye billing al usuario."""
    resp = client.post("/api/v1/datasets/load", json={
        "dataset_id": "ORG/test", "pii_checked": True, "contamination_checked": True
    })
    data = resp.get_json()
    assert "billing" in data
    assert data["billing"]["charged_to"] == "mock_admin"


def test_space_billing_info(client):
    """Crear space incluye billing al usuario."""
    resp = client.post("/api/v1/spaces", json={"name": "billing-space", "sdk": "gradio"})
    data = resp.get_json()
    assert "billing" in data
    assert data["billing"]["charged_to"] == "mock_admin"


# --- HFAuth unit tests ---

def test_hf_auth_mock_viewer():
    from hf_auth import HFAuth, HFRole
    auth = HFAuth(backend="mock")
    success, session, error = auth.authenticate("hf_mock_token_viewer")
    assert success
    assert session.role == HFRole.VIEWER
    assert session.hf_username == "mock_viewer"


def test_hf_auth_mock_user():
    from hf_auth import HFAuth, HFRole
    auth = HFAuth(backend="mock")
    success, session, error = auth.authenticate("hf_mock_token_user")
    assert success
    assert session.role == HFRole.USER


def test_hf_auth_mock_developer():
    from hf_auth import HFAuth, HFRole
    auth = HFAuth(backend="mock")
    success, session, error = auth.authenticate("hf_mock_token_developer")
    assert success
    assert session.role == HFRole.DEVELOPER


def test_hf_auth_mock_admin():
    from hf_auth import HFAuth, HFRole
    auth = HFAuth(backend="mock")
    success, session, error = auth.authenticate("hf_mock_token_admin")
    assert success
    assert session.role == HFRole.ADMIN


def test_hf_auth_invalid_token():
    from hf_auth import HFAuth
    auth = HFAuth(backend="mock")
    success, session, error = auth.authenticate("hf_invalid")
    assert not success
    assert "Invalid" in error


def test_hf_auth_empty_token():
    from hf_auth import HFAuth
    auth = HFAuth(backend="mock")
    success, session, error = auth.authenticate("")
    assert not success
    assert "Missing" in error


def test_hf_auth_session_reuse():
    from hf_auth import HFAuth
    auth = HFAuth(backend="mock")
    success1, session1, _ = auth.authenticate("hf_mock_token_user")
    success2, session2, _ = auth.authenticate("hf_mock_token_user")
    assert success1 and success2
    assert session1.session_id == session2.session_id  # misma sesión reutilizada


def test_hf_auth_logout():
    from hf_auth import HFAuth
    auth = HFAuth(backend="mock")
    success, session, _ = auth.authenticate("hf_mock_token_user")
    assert auth.logout(session.session_id)
    assert auth.get_session(session.session_id) is None


def test_hf_auth_authorize():
    from hf_auth import HFAuth, HFRole
    auth = HFAuth(backend="mock")
    _, session, _ = auth.authenticate("hf_mock_token_admin")
    assert auth.authorize(session, "endpoints:delete")
    assert auth.authorize(session, "models:train")


def test_hf_auth_authorize_viewer_denied():
    from hf_auth import HFAuth
    auth = HFAuth(backend="mock")
    _, session, _ = auth.authenticate("hf_mock_token_viewer")
    assert not auth.authorize(session, "endpoints:create")
    assert not auth.authorize(session, "models:train")


def test_hf_auth_set_role():
    from hf_auth import HFAuth, HFRole
    auth = HFAuth(backend="mock")
    _, session, _ = auth.authenticate("hf_mock_token_user")
    assert auth.set_role(session.session_id, HFRole.ADMIN)
    updated = auth.get_session(session.session_id)
    assert updated.role == HFRole.ADMIN


def test_hf_auth_list_sessions():
    from hf_auth import HFAuth
    auth = HFAuth(backend="mock")
    auth.authenticate("hf_mock_token_user")
    auth.authenticate("hf_mock_token_admin")
    sessions = auth.list_sessions()
    assert len(sessions) >= 2


# --- Role permissions ---

def test_viewer_permissions():
    from hf_auth import HFRole, ROLE_PERMISSIONS
    perms = ROLE_PERMISSIONS[HFRole.VIEWER]
    assert "inference:read" in perms
    assert "models:download" in perms
    assert "models:train" not in perms
    assert "endpoints:create" not in perms


def test_user_permissions():
    from hf_auth import HFRole, ROLE_PERMISSIONS
    perms = ROLE_PERMISSIONS[HFRole.USER]
    assert "inference:read" in perms
    assert "models:adapt" in perms
    assert "models:train" not in perms
    assert "endpoints:create" not in perms


def test_developer_permissions():
    from hf_auth import HFRole, ROLE_PERMISSIONS
    perms = ROLE_PERMISSIONS[HFRole.DEVELOPER]
    assert "models:train" in perms
    assert "endpoints:create" in perms
    assert "endpoints:delete" not in perms
    assert "training:promote" not in perms


def test_admin_permissions():
    from hf_auth import HFRole, ROLE_PERMISSIONS
    perms = ROLE_PERMISSIONS[HFRole.ADMIN]
    assert "endpoints:delete" in perms
    assert "training:promote" in perms
    assert "models:train" in perms
