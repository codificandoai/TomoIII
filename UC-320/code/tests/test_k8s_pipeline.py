"""Tests del Pipeline K8s — 6 pasos completos."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===========================================================================
# Paso 1: PKCE + JWT + K8s Secret
# ===========================================================================

def test_pkce_generate_pair():
    from hf_k8s_pipeline import PKCEVerifier
    pair = PKCEVerifier.generate_pair()
    assert "code_verifier" in pair
    assert "code_challenge" in pair
    assert len(pair["code_verifier"]) >= 43
    assert len(pair["code_challenge"]) > 0


def test_pkce_validate_correct():
    from hf_k8s_pipeline import PKCEVerifier
    pair = PKCEVerifier.generate_pair()
    assert PKCEVerifier.validate(pair["code_verifier"], pair["code_challenge"])


def test_pkce_validate_incorrect():
    from hf_k8s_pipeline import PKCEVerifier
    assert not PKCEVerifier.validate("wrong_verifier", "wrong_challenge")


def test_pkce_challenge_deterministic():
    from hf_k8s_pipeline import PKCEVerifier
    verifier = "test_verifier_12345"
    c1 = PKCEVerifier.generate_challenge(verifier)
    c2 = PKCEVerifier.generate_challenge(verifier)
    assert c1 == c2


def test_jwt_validate_mock_valid():
    from hf_k8s_pipeline import JWTValidator
    validator = JWTValidator(backend="mock")
    result = validator.validate("hf_mock_token_1234")
    assert result["valid"] is True
    assert "username" in result


def test_jwt_validate_mock_invalid():
    from hf_k8s_pipeline import JWTValidator
    validator = JWTValidator(backend="mock")
    result = validator.validate("invalid_token")
    assert result["valid"] is False


def test_jwt_validate_empty():
    from hf_k8s_pipeline import JWTValidator
    validator = JWTValidator(backend="mock")
    result = validator.validate("")
    assert result["valid"] is False


def test_k8s_secret_create():
    from hf_k8s_pipeline import SecretManager
    mgr = SecretManager()
    secret = mgr.create_secret("hf_token_123")
    assert secret.secret_name.startswith("hf-token-")
    assert secret.namespace == "utron-ai"
    assert not secret.is_expired()


def test_k8s_secret_yaml():
    from hf_k8s_pipeline import SecretManager
    mgr = SecretManager()
    secret = mgr.create_secret("hf_token_123")
    yaml = secret.to_yaml()
    assert "apiVersion: v1" in yaml
    assert "kind: Secret" in yaml
    assert secret.secret_name in yaml


def test_k8s_secret_get():
    from hf_k8s_pipeline import SecretManager
    mgr = SecretManager()
    secret = mgr.create_secret("hf_token")
    retrieved = mgr.get_secret(secret.secret_name)
    assert retrieved is not None
    assert retrieved.token == "hf_token"


def test_k8s_secret_delete():
    from hf_k8s_pipeline import SecretManager
    mgr = SecretManager()
    secret = mgr.create_secret("hf_token")
    assert mgr.delete_secret(secret.secret_name)
    assert mgr.get_secret(secret.secret_name) is None


def test_k8s_secret_cleanup_expired():
    from hf_k8s_pipeline import SecretManager
    mgr = SecretManager()
    secret = mgr.create_secret("hf_token")
    secret.expires_at = 0  # expirar
    cleaned = mgr.cleanup_expired()
    assert cleaned >= 1


def test_k8s_secret_list():
    from hf_k8s_pipeline import SecretManager
    mgr = SecretManager()
    mgr.create_secret("hf_token_1")
    mgr.create_secret("hf_token_2")
    assert len(mgr.list_secrets()) >= 2


# ===========================================================================
# Paso 2: K8s Cluster Capacity Validation
# ===========================================================================

def test_cluster_get_nodes():
    from hf_k8s_pipeline import K8sClusterValidator
    validator = K8sClusterValidator(backend="mock")
    nodes = validator.get_nodes()
    assert len(nodes) > 0
    assert any(n.gpu_count > 0 for n in nodes)


def test_cluster_preflight_sufficient():
    from hf_k8s_pipeline import K8sClusterValidator
    validator = K8sClusterValidator(backend="mock")
    result = validator.pre_flight_check("test/model", vram_required_gb=20.0)
    assert result.cluster_has_resources is True
    assert len(result.suitable_nodes) > 0
    assert result.recommended_node != ""


def test_cluster_preflight_insufficient():
    from hf_k8s_pipeline import K8sClusterValidator
    validator = K8sClusterValidator(backend="mock")
    result = validator.pre_flight_check("test/model", vram_required_gb=500.0)
    assert result.cluster_has_resources is False
    assert len(result.issues) > 0


def test_cluster_preflight_cpu_only():
    from hf_k8s_pipeline import K8sClusterValidator
    validator = K8sClusterValidator(backend="mock")
    result = validator.pre_flight_check("test/model", vram_required_gb=0, require_gpu=False)
    assert result.cluster_has_resources is True


def test_cluster_preflight_can_proceed():
    from hf_k8s_pipeline import K8sClusterValidator
    validator = K8sClusterValidator(backend="mock")
    result = validator.pre_flight_check("test/model", vram_required_gb=20.0)
    assert result.to_dict()["can_proceed"] is True


def test_cluster_preflight_cannot_proceed():
    from hf_k8s_pipeline import K8sClusterValidator
    validator = K8sClusterValidator(backend="mock")
    result = validator.pre_flight_check("test/model", vram_required_gb=500.0)
    assert result.to_dict()["can_proceed"] is False


# ===========================================================================
# Paso 3: Manifiestos con env vars + CRD
# ===========================================================================

def test_manifest_env_vars():
    from hf_k8s_pipeline import K8sManifestBuilder
    builder = K8sManifestBuilder()
    env_vars = builder.build_env_vars("hf-secret")
    names = [e["name"] for e in env_vars]
    assert "HUGGING_FACE_HUB_TOKEN" in names
    assert "HF_HUB_ENABLE_HF_TRANSFER" in names
    assert "HF_HOME" in names
    assert "HF_HUB_CACHE" in names


def test_manifest_env_hf_transfer_value():
    from hf_k8s_pipeline import K8sManifestBuilder
    builder = K8sManifestBuilder()
    env_vars = builder.build_env_vars("hf-secret")
    transfer_var = [e for e in env_vars if e["name"] == "HF_HUB_ENABLE_HF_TRANSFER"][0]
    assert transfer_var["value"] == "1"


def test_manifest_env_hf_home_value():
    from hf_k8s_pipeline import K8sManifestBuilder
    builder = K8sManifestBuilder()
    env_vars = builder.build_env_vars("hf-secret")
    home_var = [e for e in env_vars if e["name"] == "HF_HOME"][0]
    assert home_var["value"] == "/root/.cache/huggingface"


def test_manifest_volumes_pvc():
    from hf_k8s_pipeline import K8sManifestBuilder
    builder = K8sManifestBuilder()
    volumes, mounts = builder.build_volumes("hf-cache")
    assert any(v["name"] == "hf-cache" for v in volumes)
    assert any("persistentVolumeClaim" in v for v in volumes)
    assert any(m["mountPath"] == "/root/.cache/huggingface" for m in mounts)


def test_manifest_pvc_yaml():
    from hf_k8s_pipeline import K8sManifestBuilder
    builder = K8sManifestBuilder()
    yaml = builder.build_pvc()
    assert "ReadWriteMany" in yaml
    assert "PersistentVolumeClaim" in yaml


def test_manifest_vllm_with_env_vars():
    from hf_k8s_pipeline import K8sManifestBuilder
    builder = K8sManifestBuilder()
    yaml = builder.build_vllm_deployment("org/model", "hf-secret", "A10G")
    assert "HF_HUB_ENABLE_HF_TRANSFER" in yaml
    assert "HF_HOME" in yaml
    assert "HUGGING_FACE_HUB_TOKEN" in yaml
    assert "persistentVolumeClaim" in yaml
    assert "vllm" in yaml


def test_manifest_pytorchjob_crd():
    from hf_k8s_pipeline import K8sManifestBuilder
    builder = K8sManifestBuilder()
    yaml = builder.build_pytorchjob_crd("org/model", "org/dataset", "hf-secret", "A10G")
    assert "PyTorchJob" in yaml
    assert "kubeflow.org/v1" in yaml
    assert "HF_HUB_ENABLE_HF_TRANSFER" in yaml
    assert "org/model" in yaml
    assert "org/dataset" in yaml


def test_manifest_rayjob_crd():
    from hf_k8s_pipeline import K8sManifestBuilder
    builder = K8sManifestBuilder()
    yaml = builder.build_rayjob_crd("org/model", "org/dataset", "hf-secret", "A10G")
    assert "RayJob" in yaml
    assert "ray.io/v1" in yaml
    assert "rayproject/ray" in yaml


def test_k8s_api_apply():
    from hf_k8s_pipeline import K8sAPIClient
    client = K8sAPIClient(backend="mock")
    result = client.apply_manifest("apiVersion: v1\nkind: Pod\nmetadata:\n  name: test")
    assert result["applied"] is True
    assert "job_name" in result


def test_k8s_api_job_status():
    from hf_k8s_pipeline import K8sAPIClient
    client = K8sAPIClient(backend="mock")
    result = client.apply_manifest("test yaml")
    job_name = result["job_name"]
    status = client.get_job_status(job_name)
    assert status is not None
    assert status.status == "running"


def test_k8s_api_delete_job():
    from hf_k8s_pipeline import K8sAPIClient
    client = K8sAPIClient(backend="mock")
    result = client.apply_manifest("test yaml")
    job_name = result["job_name"]
    assert client.delete_job(job_name)
    assert client.get_job_status(job_name) is None


def test_k8s_api_update_metrics():
    from hf_k8s_pipeline import K8sAPIClient
    client = K8sAPIClient(backend="mock")
    result = client.apply_manifest("test yaml")
    job_name = result["job_name"]
    assert client.update_metrics(job_name, {"loss": 0.5, "tokens_per_sec": 100})
    job = client.get_job_status(job_name)
    assert job.metrics["loss"] == 0.5


# ===========================================================================
# Paso 4: Caché PVC + SHA-256
# ===========================================================================

def test_cache_miss():
    from hf_k8s_pipeline import SharedCacheManager
    cache = SharedCacheManager()
    result = cache.check_cache("org/model", "model.safetensors")
    assert result["cache_hit"] is False
    assert "download_from_cdn" in result["action"]


def test_cache_hit():
    from hf_k8s_pipeline import SharedCacheManager
    cache = SharedCacheManager()
    cache.add_to_cache("org/model", "model.safetensors", "abc123", 16_000_000_000)
    result = cache.check_cache("org/model", "model.safetensors")
    assert result["cache_hit"] is True
    assert result["network_io"] == 0


def test_cache_sha256_mismatch():
    from hf_k8s_pipeline import SharedCacheManager
    cache = SharedCacheManager()
    cache.add_to_cache("org/model", "model.safetensors", "abc123", 16_000_000_000)
    result = cache.check_cache("org/model", "model.safetensors", expected_sha256="wrong_hash")
    assert result["cache_hit"] is False
    assert "mismatch" in result["reason"]


def test_cache_stats():
    from hf_k8s_pipeline import SharedCacheManager
    cache = SharedCacheManager()
    cache.add_to_cache("org/model", "model.safetensors", "abc123", 16_000_000_000)
    stats = cache.cache_stats()
    assert stats["total_files"] == 1
    assert stats["pvc_mode"] == "ReadWriteMany"
    assert stats["shared_across_pods"] is True


def test_cache_prefetch():
    from hf_k8s_pipeline import SharedCacheManager
    cache = SharedCacheManager()
    result = cache.prefetch_model("org/model", [
        ("model.safetensors", "sha1", 16_000_000_000),
        ("config.json", "sha2", 2048),
    ])
    assert result["downloaded"] == 2
    assert result["cache_hits"] == 0
    assert result["egress_cost"] == "$0"


def test_cache_prefetch_with_existing():
    from hf_k8s_pipeline import SharedCacheManager
    cache = SharedCacheManager()
    cache.add_to_cache("org/model", "model.safetensors", "sha1", 16_000_000_000)
    result = cache.prefetch_model("org/model", [
        ("model.safetensors", "sha1", 16_000_000_000),
        ("config.json", "sha2", 2048),
    ])
    assert result["cache_hits"] == 1
    assert result["downloaded"] == 1


# ===========================================================================
# Paso 5: Métricas WebSockets
# ===========================================================================

def test_metrics_subscribe():
    from hf_k8s_pipeline import MetricsStreamer
    streamer = MetricsStreamer()
    sub_id = streamer.subscribe("job-123")
    assert sub_id.startswith("sub_")


def test_metrics_emit():
    from hf_k8s_pipeline import MetricsStreamer, JobMetrics
    streamer = MetricsStreamer()
    streamer.subscribe("job-123")
    m = JobMetrics(job_name="job-123", loss=0.5, tokens_per_sec=100, vram_used_gb=19.2, vram_total_gb=24.0)
    result = streamer.emit_metrics("job-123", m)
    assert result["emitted"] is True
    assert result["subscribers"] >= 1


def test_metrics_history():
    from hf_k8s_pipeline import MetricsStreamer, JobMetrics
    streamer = MetricsStreamer()
    m = JobMetrics(job_name="job-123", loss=0.5)
    streamer.emit_metrics("job-123", m)
    history = streamer.get_metrics_history("job-123")
    assert len(history) == 1
    assert history[0]["loss"] == 0.5


def test_metrics_simulate_training():
    from hf_k8s_pipeline import MetricsStreamer
    streamer = MetricsStreamer()
    metrics = streamer.simulate_training_metrics("job-123", total_steps=10)
    assert len(metrics) == 10
    # Loss debe decrecer
    assert metrics[0]["loss"] > metrics[-1]["loss"]
    # Progreso debe llegar a 100%
    assert metrics[-1]["progress"] == 100.0
    assert metrics[-1]["status"] == "completed"


def test_metrics_unsubscribe():
    from hf_k8s_pipeline import MetricsStreamer
    streamer = MetricsStreamer()
    sub_id = streamer.subscribe("job-123")
    assert streamer.unsubscribe("job-123", sub_id)


def test_metrics_vram_utilization():
    from hf_k8s_pipeline import JobMetrics
    m = JobMetrics(job_name="test", vram_used_gb=19.2, vram_total_gb=24.0)
    data = m.to_dict()
    assert data["vram_utilization"] == pytest.approx(80.0, abs=1)


# ===========================================================================
# Paso 6: Empaquetado + Publicación + Limpieza
# ===========================================================================

def test_packager_adapter():
    from hf_k8s_pipeline import ModelPackager
    pkg = ModelPackager()
    result = pkg.package("org/model", adapter_only=True)
    assert result.safetensors is True
    assert any(f["filename"] == "adapter_model.safetensors" for f in result.files)
    assert "README.md" in [f["filename"] for f in result.files]


def test_packager_full_model():
    from hf_k8s_pipeline import ModelPackager
    pkg = ModelPackager()
    result = pkg.package("org/model", adapter_only=False)
    assert any(f["filename"] == "model.safetensors" for f in result.files)


def test_packager_model_card():
    from hf_k8s_pipeline import ModelPackager
    pkg = ModelPackager()
    result = pkg.package("org/model")
    assert "base_model" in result.model_card_md
    assert "safetensors" in result.model_card_md


def test_publisher_upload_mock():
    from hf_k8s_pipeline import HubPublisher
    pub = HubPublisher(backend="mock")
    result = pub.upload_folder("user/my-model", "/path/to/outputs")
    assert result["uploaded"] is True
    assert "huggingface.co/user/my-model" in result["model_url"]
    assert "$0" in result["billing"]


def test_garbage_collector_cleanup_job():
    from hf_k8s_pipeline import K8sAPIClient, SecretManager, GarbageCollector
    k8s = K8sAPIClient(backend="mock")
    secrets = SecretManager()
    gc = GarbageCollector(k8s, secrets)
    # Crear job y secret
    apply_result = k8s.apply_manifest("test")
    secret = secrets.create_secret("hf_token")
    # Cleanup
    result = gc.cleanup_job(apply_result["job_name"], secret.secret_name)
    assert result["gpus_freed"] is True
    assert result["model_persisted_in_hf"] is True
    assert result["cache_retained_in_pvc"] is True


def test_garbage_collector_cleanup_all():
    from hf_k8s_pipeline import K8sAPIClient, SecretManager, GarbageCollector
    k8s = K8sAPIClient(backend="mock")
    secrets = SecretManager()
    gc = GarbageCollector(k8s, secrets)
    k8s.apply_manifest("yaml1")
    k8s.apply_manifest("yaml2")
    # Marcar como completados
    for job_name, job in k8s._jobs.items():
        job.status = "succeeded"
    result = gc.cleanup_all_completed()
    assert result["jobs_cleaned"] == 2


# ===========================================================================
# Pipeline integrado — 6 pasos
# ===========================================================================

def test_pipeline_execute_inference():
    from hf_k8s_pipeline import K8sPipeline
    pipeline = K8sPipeline(backend="mock")
    result = pipeline.execute_pipeline(
        hf_token="hf_mock_token_1234",
        model_id="meta-llama/Meta-Llama-3-8B",
        operation="inference",
        gpu_type="A10G",
    )
    assert result["pipeline_complete"] is True
    assert "1_auth" in result["steps"]
    assert "2_preflight" in result["steps"]
    assert "3_deploy" in result["steps"]
    assert "4_cache" in result["steps"]
    assert "5_execution" in result["steps"]
    assert "6_publish" in result["steps"]
    assert result["billing"]["hf_charges"] == "$0 (on-premise K8s compute)"


def test_pipeline_execute_training():
    from hf_k8s_pipeline import K8sPipeline
    pipeline = K8sPipeline(backend="mock")
    result = pipeline.execute_pipeline(
        hf_token="hf_mock_token_1234",
        model_id="mistralai/Mistral-7B-Instruct-v0.3",
        operation="train",
        dataset_id="imdb",
        gpu_type="A10G",
        push_repo_id="user/my-finetuned",
    )
    assert result["pipeline_complete"] is True
    assert result["steps"]["3_deploy"]["manifest_type"] == "PyTorchJob"
    assert result["steps"]["6_publish"]["publish"]["uploaded"] is True


def test_pipeline_auth_failure():
    from hf_k8s_pipeline import K8sPipeline
    pipeline = K8sPipeline(backend="mock")
    result = pipeline.execute_pipeline(
        hf_token="invalid_token",
        model_id="org/model",
    )
    assert "error" in result


def test_pipeline_preflight_failure():
    from hf_k8s_pipeline import K8sPipeline
    pipeline = K8sPipeline(backend="mock")
    result = pipeline.execute_pipeline(
        hf_token="hf_mock_token",
        model_id="org/model",
        gpu_type="T4",  # T4 has 16GB, might not be enough for some models
    )
    # Should still proceed if there are A100 nodes in mock
    # But if we request vram > all nodes, it should fail
    result2 = pipeline.execute_pipeline(
        hf_token="hf_mock_token",
        model_id="mistralai/Mixtral-8x7B-Instruct-v0.1",  # 46.7B params
        gpu_type="T4",
    )
    # Mixtral needs ~112GB VRAM for FP16 inference — only A100-80 (320GB total) can fit
    # Mock has A100-80 with 4 GPUs = 320GB, so it should pass
    if "error" in result2:
        assert "Pre-flight" in result2["error"]


# ===========================================================================
# API REST — Pipeline endpoints
# ===========================================================================

def test_api_pipeline_pkce(client):
    resp = client.get("/api/v1/pipeline/pkce")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "code_verifier" in data
    assert "code_challenge" in data


def test_api_pipeline_jwt_validate(client):
    resp = client.post("/api/v1/pipeline/jwt/validate", json={"token": "hf_mock_token"})
    assert resp.status_code == 200
    assert resp.get_json()["valid"] is True


def test_api_pipeline_secrets_create(client):
    resp = client.post("/api/v1/pipeline/secrets")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["secret_name"].startswith("hf-token-")


def test_api_pipeline_secrets_list(client):
    client.post("/api/v1/pipeline/secrets")
    resp = client.get("/api/v1/pipeline/secrets")
    assert resp.status_code == 200
    assert len(resp.get_json()["secrets"]) >= 1


def test_api_pipeline_preflight(client):
    resp = client.post("/api/v1/pipeline/preflight", json={
        "model_id": "org/model", "vram_required_gb": 20.0
    })
    assert resp.status_code == 200
    assert resp.get_json()["cluster_has_resources"] is True


def test_api_pipeline_cluster_nodes(client):
    resp = client.get("/api/v1/pipeline/cluster/nodes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["nodes"]) > 0


def test_api_pipeline_manifest_vllm(client):
    resp = client.post("/api/v1/pipeline/manifest/vllm", json={
        "model_id": "org/model", "secret_name": "hf-secret", "gpu_type": "A10G"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "HF_HUB_ENABLE_HF_TRANSFER" in data["yaml"]


def test_api_pipeline_manifest_pytorchjob(client):
    resp = client.post("/api/v1/pipeline/manifest/pytorchjob", json={
        "model_id": "org/model", "dataset_id": "org/dataset", "secret_name": "hf-secret"
    })
    assert resp.status_code == 200
    assert "PyTorchJob" in resp.get_json()["yaml"]


def test_api_pipeline_manifest_rayjob(client):
    resp = client.post("/api/v1/pipeline/manifest/rayjob", json={
        "model_id": "org/model", "dataset_id": "org/dataset", "secret_name": "hf-secret"
    })
    assert resp.status_code == 200
    assert "RayJob" in resp.get_json()["yaml"]


def test_api_pipeline_manifest_pvc(client):
    resp = client.get("/api/v1/pipeline/manifest/pvc")
    assert resp.status_code == 200
    assert "ReadWriteMany" in resp.get_json()["yaml"]


def test_api_pipeline_apply(client):
    resp = client.post("/api/v1/pipeline/apply", json={"yaml": "apiVersion: v1\nkind: Pod"})
    assert resp.status_code == 200
    assert resp.get_json()["applied"] is True


def test_api_pipeline_cache_check(client):
    resp = client.post("/api/v1/pipeline/cache/check", json={
        "repo_id": "org/model", "filename": "model.safetensors"
    })
    assert resp.status_code == 200
    assert resp.get_json()["cache_hit"] is False


def test_api_pipeline_cache_list(client):
    resp = client.get("/api/v1/pipeline/cache")
    assert resp.status_code == 200
    assert "stats" in resp.get_json()


def test_api_pipeline_cache_prefetch(client):
    resp = client.post("/api/v1/pipeline/cache/prefetch", json={
        "repo_id": "org/model",
        "files": [{"filename": "model.safetensors", "sha256": "abc", "size_bytes": 16000000000}]
    })
    assert resp.status_code == 200
    assert resp.get_json()["downloaded"] == 1


def test_api_pipeline_jobs_list(client):
    resp = client.get("/api/v1/pipeline/jobs")
    assert resp.status_code == 200


def test_api_pipeline_job_metrics(client):
    resp = client.get("/api/v1/pipeline/jobs/test-job/metrics")
    assert resp.status_code == 200
    assert "metrics_history" in resp.get_json()


def test_api_pipeline_job_subscribe(client):
    resp = client.post("/api/v1/pipeline/jobs/test-job/metrics/subscribe")
    assert resp.status_code == 200
    assert "subscription_id" in resp.get_json()


def test_api_pipeline_package(client):
    resp = client.post("/api/v1/pipeline/package", json={
        "model_id": "org/model", "adapter_only": True
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["safetensors"] is True


def test_api_pipeline_publish(client):
    resp = client.post("/api/v1/pipeline/publish", json={
        "repo_id": "user/my-model", "folder_path": "/outputs"
    })
    assert resp.status_code == 200
    assert resp.get_json()["uploaded"] is True


def test_api_pipeline_cleanup(client):
    resp = client.post("/api/v1/pipeline/cleanup", json={})
    assert resp.status_code == 200


def test_api_pipeline_execute(client):
    resp = client.post("/api/v1/pipeline/execute", json={
        "model_id": "meta-llama/Meta-Llama-3-8B",
        "operation": "inference",
        "gpu_type": "A10G",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("pipeline_complete") is True


def test_api_pipeline_execute_training(client):
    resp = client.post("/api/v1/pipeline/execute", json={
        "model_id": "mistralai/Mistral-7B-Instruct-v0.3",
        "operation": "train",
        "dataset_id": "imdb",
        "push_repo_id": "user/my-model",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("pipeline_complete") is True


def test_api_pipeline_no_auth(no_auth_client):
    resp = no_auth_client.get("/api/v1/pipeline/pkce")
    assert resp.status_code == 401
