"""Tests de los procesos de integración HF Hub: catálogo, descarga, scripts, OAuth, gated."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===========================================================================
# 1. Catálogo — Búsqueda y Metadatos (HF Hub API)
# ===========================================================================

def test_catalog_list_models():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    models = browser.list_models()
    assert len(models) > 0
    assert all(m["type"] == "model" for m in models)


def test_catalog_list_models_filter_task():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    models = browser.list_models(task="text-generation")
    assert all(m["pipeline_tag"] == "text-generation" or "text-generation" in m.get("tags", []) for m in models)


def test_catalog_list_models_filter_search():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    models = browser.list_models(search="finance")
    assert any("finance" in m["id"].lower() or "finance" in [t.lower() for t in m.get("tags", [])] for m in models)


def test_catalog_list_models_filter_license():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    models = browser.list_models(license="MIT")
    assert all(m["license"] == "MIT" for m in models)


def test_catalog_list_models_filter_author():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    models = browser.list_models(author="ProsusAI")
    assert all(m["author"] == "ProsusAI" for m in models)


def test_catalog_list_models_limit():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    models = browser.list_models(limit=2)
    assert len(models) <= 2


def test_catalog_list_datasets():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    datasets = browser.list_datasets()
    assert len(datasets) > 0
    assert all(d["type"] == "dataset" for d in datasets)


def test_catalog_list_datasets_search():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    datasets = browser.list_datasets(search="finance")
    assert len(datasets) > 0
    assert any("finance" in d["id"].lower() or "finance" in [t.lower() for t in d.get("tags", [])] for d in datasets)


def test_catalog_list_spaces():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    spaces = browser.list_spaces()
    assert len(spaces) > 0
    assert all(s["type"] == "space" for s in spaces)


def test_catalog_search_all():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    results = browser.search_all("finance")
    assert "models" in results
    assert "datasets" in results
    assert "spaces" in results


def test_catalog_get_model():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    model = browser.get_model("ProsusAI/finbert")
    assert model is not None
    assert model["id"] == "ProsusAI/finbert"


def test_catalog_get_model_not_found():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    model = browser.get_model("nonexistent/model")
    assert model is None


def test_catalog_get_dataset():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    ds = browser.get_dataset("imdb")
    assert ds is not None
    assert ds["id"] == "imdb"


def test_catalog_get_space():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    sp = browser.get_space("gradio/hello_world")
    assert sp is not None


def test_catalog_cache():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    # Primera llamada
    models1 = browser.list_models()
    # Segunda llamada (debe usar cache)
    models2 = browser.list_models()
    assert models1 == models2


# ===========================================================================
# 2. Gated Models
# ===========================================================================

def test_gated_model_check_gated():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    result = browser.check_gated("meta-llama/Meta-Llama-3-8B")
    assert result["gated"] is True
    assert "message" in result


def test_gated_model_check_not_gated():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    result = browser.check_gated("ProsusAI/finbert")
    assert result["gated"] is False
    assert result["access"] is True


def test_gated_model_not_found():
    from hf_catalog import HFCatalogBrowser
    browser = HFCatalogBrowser(backend="mock")
    result = browser.check_gated("nonexistent/model")
    assert result["exists"] is False


# ===========================================================================
# 3. Descarga — URLs resolve y code snippets
# ===========================================================================

def test_download_resolve_url():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    result = dl.resolve_url("org/model", "model.safetensors")
    assert "huggingface.co/org/model/resolve/main/model.safetensors" in result["url"]
    assert result["filename"] == "model.safetensors"


def test_download_resolve_url_with_revision():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    result = dl.resolve_url("org/model", "config.json", revision="v2")
    assert "/resolve/v2/config.json" in result["url"]


def test_download_resolve_url_with_token():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager(token="hf_user_token_12345678")
    result = dl.resolve_url("org/model", "model.safetensors")
    assert result["auth_required"] is True
    assert "curl" in result["curl_command"]


def test_download_list_files():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    result = dl.list_files("meta-llama/Meta-Llama-3-8B")
    assert "model.safetensors" in " ".join(result["files"])
    assert len(result["download_urls"]) > 0


def test_download_list_files_diffusion():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    result = dl.list_files("stabilityai/stable-diffusion-xl-base-1.0")
    assert "model_index.json" in result["files"]


def test_download_transformers_snippet():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    snippet = dl.generate_transformers_snippet("org/model", "text-generation")
    assert "AutoModelForCausalLM" in snippet.code
    assert "org/model" in snippet.code
    assert snippet.language == "python"


def test_download_transformers_snippet_embeddings():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    snippet = dl.generate_transformers_snippet("org/model", "feature-extraction")
    assert "AutoModel" in snippet.code


def test_download_transformers_snippet_classification():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    snippet = dl.generate_transformers_snippet("org/model", "text-classification")
    assert "AutoModelForSequenceClassification" in snippet.code


def test_download_diffusers_snippet():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    snippet = dl.generate_diffusers_snippet("stabilityai/sdxl")
    assert "StableDiffusionPipeline" in snippet.code
    assert "stabilityai/sdxl" in snippet.code


def test_download_datasets_snippet():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    snippet = dl.generate_datasets_snippet("imdb")
    assert "load_dataset" in snippet.code
    assert "imdb" in snippet.code


def test_download_hf_hub_snippet():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    snippet = dl.generate_hf_hub_snippet("org/model")
    assert "hf_hub_download" in snippet.code
    assert "org/model" in snippet.code


def test_download_get_all_snippets():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    snippets = dl.get_all_snippets("org/model", "text-generation")
    assert len(snippets) >= 2


def test_download_get_all_snippets_diffusion():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    snippets = dl.get_all_snippets("org/model", "text-to-image")
    assert any("diffusers" in s.code for s in snippets)


def test_download_get_download_info():
    from hf_download import HFDownloadManager
    dl = HFDownloadManager()
    info = dl.get_download_info("org/model")
    assert "files" in info
    assert "download_urls" in info
    assert "code_snippets" in info
    assert "auth_note" in info


# ===========================================================================
# 4. Script Generator — Fine-Tuning LoRA/PEFT
# ===========================================================================

def test_script_generator_lora():
    from hf_script_generator import FineTuneConfig, ScriptGenerator
    config = FineTuneConfig(base_model="mistralai/Mistral-7B", dataset_id="imdb")
    gen = ScriptGenerator()
    script = gen.generate_lora_script(config)
    assert "LoraConfig" in script
    assert "mistralai/Mistral-7B" in script
    assert "imdb" in script
    assert "get_peft_model" in script


def test_script_generator_qlora():
    from hf_script_generator import FineTuneConfig, ScriptGenerator
    config = FineTuneConfig(base_model="mistralai/Mistral-7B", dataset_id="imdb", method="qlora")
    gen = ScriptGenerator()
    script = gen.generate_qlora_script(config)
    assert "BitsAndBytesConfig" in script
    assert "load_in_4bit" in script


def test_script_generator_classification():
    from hf_script_generator import FineTuneConfig, ScriptGenerator
    config = FineTuneConfig(
        base_model="ProsusAI/finbert", dataset_id="imdb",
        task="text-classification",
    )
    gen = ScriptGenerator()
    script = gen.generate_classification_script(config)
    assert "AutoModelForSequenceClassification" in script
    assert "ProsusAI/finbert" in script


def test_script_generator_notebook():
    from hf_script_generator import FineTuneConfig, ScriptGenerator
    config = FineTuneConfig(base_model="org/model", dataset_id="ds")
    gen = ScriptGenerator()
    notebook_json = gen.generate_notebook(config)
    notebook = json.loads(notebook_json)
    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) >= 3


def test_script_generator_generate_full():
    from hf_script_generator import FineTuneConfig, ScriptGenerator
    config = FineTuneConfig(
        base_model="org/model", dataset_id="ds",
        push_to_hub=True, hub_repo_id="user/my-model",
    )
    gen = ScriptGenerator()
    result = gen.generate(config)
    assert "script" in result
    assert "notebook" in result
    assert "filename" in result
    assert "billing_note" in result
    assert "transformers" in result["libraries"]


def test_script_generator_push_to_hub():
    from hf_script_generator import FineTuneConfig, ScriptGenerator
    config = FineTuneConfig(
        base_model="org/model", dataset_id="ds",
        push_to_hub=True, hub_repo_id="user/my-model",
    )
    gen = ScriptGenerator()
    script = gen.generate_lora_script(config)
    assert "push_to_hub" in script
    assert "user/my-model" in script


# ===========================================================================
# 5. OAuth — Login con Hugging Face
# ===========================================================================

def test_oauth_get_authorization_url():
    from hf_oauth import HFOAuth
    oauth = HFOAuth(backend="mock")
    result = oauth.get_authorization_url()
    assert "authorization_url" in result
    assert "huggingface.co/oauth/authorize" in result["authorization_url"]
    assert "state" in result
    assert "client_id" in result["authorization_url"]


def test_oauth_authorization_url_with_scopes():
    from hf_oauth import HFOAuth
    oauth = HFOAuth(backend="mock")
    result = oauth.get_authorization_url(scopes=["openid", "profile", "inference-api"])
    assert "openid" in result["authorization_url"]
    assert "inference-api" in result["authorization_url"]


def test_oauth_exchange_code_mock():
    from hf_oauth import HFOAuth
    oauth = HFOAuth(backend="mock")
    # Primero obtener state
    auth = oauth.get_authorization_url()
    state = auth["state"]
    # Intercambiar code mock
    result = oauth.exchange_code("mock_code_1234", state)
    assert result["success"]
    assert "user_info" in result
    assert result["user_info"].hf_username.startswith("oauth_user_")


def test_oauth_exchange_code_invalid_state():
    from hf_oauth import HFOAuth
    oauth = HFOAuth(backend="mock")
    result = oauth.exchange_code("mock_code_1234", "invalid_state")
    assert not result["success"]
    assert "Invalid" in result["error"]


def test_oauth_exchange_code_invalid_code():
    from hf_oauth import HFOAuth
    oauth = HFOAuth(backend="mock")
    auth = oauth.get_authorization_url()
    result = oauth.exchange_code("invalid_code", auth["state"])
    assert not result["success"]


def test_oauth_validate_scopes_ok():
    from hf_oauth import HFOAuth, REQUIRED_SCOPES
    oauth = HFOAuth(backend="mock")
    result = oauth.validate_scopes(REQUIRED_SCOPES, REQUIRED_SCOPES)
    assert result["valid"] is True


def test_oauth_validate_scopes_missing():
    from hf_oauth import HFOAuth, REQUIRED_SCOPES
    oauth = HFOAuth(backend="mock")
    result = oauth.validate_scopes(["openid", "profile"], REQUIRED_SCOPES)
    assert result["valid"] is False
    assert len(result["missing"]) > 0


def test_oauth_get_scopes_info():
    from hf_oauth import HFOAuth
    oauth = HFOAuth(backend="mock")
    info = oauth.get_scopes_info()
    assert "required" in info
    assert "optional" in info
    assert "billing_note" in info
    assert any(s["scope"] == "inference-api" for s in info["required"])


def test_oauth_cleanup_expired():
    from hf_oauth import HFOAuth
    oauth = HFOAuth(backend="mock")
    oauth.get_authorization_url()
    oauth.get_authorization_url()
    # Forzar expiración
    for s in oauth._states.values():
        s.created_at = 0
    cleaned = oauth.cleanup_expired_states()
    assert cleaned >= 2


def test_oauth_state_is_valid():
    from hf_oauth import OAuthState
    state = OAuthState(state="test")
    assert state.is_valid()
    state.created_at = 0
    assert not state.is_valid()


# ===========================================================================
# 6. API REST — Endpoints de catálogo, descarga, scripts, OAuth
# ===========================================================================

def test_api_catalog_models(client):
    resp = client.get("/api/v1/catalog/models")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "models" in data
    assert data["count"] > 0


def test_api_catalog_models_filter(client):
    resp = client.get("/api/v1/catalog/models?task=text-generation")
    assert resp.status_code == 200
    data = resp.get_json()
    assert all(m["pipeline_tag"] == "text-generation" for m in data["models"])


def test_api_catalog_datasets(client):
    resp = client.get("/api/v1/catalog/datasets")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "datasets" in data


def test_api_catalog_spaces(client):
    resp = client.get("/api/v1/catalog/spaces")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "spaces" in data


def test_api_catalog_search(client):
    resp = client.get("/api/v1/catalog/search?q=finance")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "results" in data
    assert "models" in data["results"]


def test_api_catalog_search_no_query(client):
    resp = client.get("/api/v1/catalog/search")
    assert resp.status_code == 400


def test_api_catalog_get_model(client):
    resp = client.get("/api/v1/catalog/models/ProsusAI/finbert")
    assert resp.status_code == 200
    assert resp.get_json()["id"] == "ProsusAI/finbert"


def test_api_catalog_get_model_not_found(client):
    resp = client.get("/api/v1/catalog/models/nonexistent/model")
    assert resp.status_code == 404


def test_api_catalog_gated(client):
    resp = client.get("/api/v1/catalog/models/meta-llama/Meta-Llama-3-8B/gated")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["gated"] is True


def test_api_download_resolve(client):
    resp = client.get("/api/v1/download/org/model/resolve?filename=model.safetensors")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "huggingface.co" in data["url"]


def test_api_download_resolve_no_filename(client):
    resp = client.get("/api/v1/download/org/model/resolve")
    assert resp.status_code == 400


def test_api_download_files(client):
    resp = client.get("/api/v1/download/org/model/files")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "files" in data
    assert "download_urls" in data


def test_api_download_info(client):
    resp = client.get("/api/v1/download/org/model/info")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "code_snippets" in data


def test_api_download_snippets(client):
    resp = client.get("/api/v1/download/org/model/snippets?task=text-generation")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["snippets"]) >= 2


def test_api_finetune_generate(client):
    resp = client.post("/api/v1/finetune/generate", json={
        "base_model": "mistralai/Mistral-7B",
        "dataset_id": "imdb",
        "method": "lora",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "script" in data
    assert "notebook" in data
    assert "LoraConfig" in data["script"]
    assert "billing_note" in data


def test_api_finetune_generate_no_model(client):
    resp = client.post("/api/v1/finetune/generate", json={"dataset_id": "imdb"})
    assert resp.status_code == 400


def test_api_oauth_login():
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        resp = c.get("/api/v1/auth/oauth/login")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "authorization_url" in data
        assert "huggingface.co/oauth/authorize" in data["authorization_url"]


def test_api_oauth_scopes():
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        resp = c.get("/api/v1/auth/oauth/scopes")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "required" in data
        assert "billing_note" in data


def test_api_oauth_callback_mock():
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        # Obtener state
        login = c.get("/api/v1/auth/oauth/login")
        state = login.get_json()["state"]
        # Callback con code mock
        resp = c.get(f"/api/v1/auth/oauth/callback?code=mock_code_1234&state={state}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"]
        assert "session" in data


def test_api_oauth_callback_no_params():
    from api_320 import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        resp = c.get("/api/v1/auth/oauth/callback")
        assert resp.status_code == 400


# ===========================================================================
# 7. Auth en endpoints de catálogo (sin token → 401)
# ===========================================================================

def test_api_catalog_no_auth(no_auth_client):
    resp = no_auth_client.get("/api/v1/catalog/models")
    assert resp.status_code == 401


def test_api_download_no_auth(no_auth_client):
    resp = no_auth_client.get("/api/v1/download/org/model/files")
    assert resp.status_code == 401


def test_api_finetune_no_auth(no_auth_client):
    resp = no_auth_client.post("/api/v1/finetune/generate", json={
        "base_model": "org/model", "dataset_id": "ds"
    })
    assert resp.status_code == 401
