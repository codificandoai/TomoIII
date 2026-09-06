"""Tests del Panel Interactivo de Modelos — 6 funcionalidades."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===========================================================================
# 1. VRAM Calculator
# ===========================================================================

def test_vram_estimate_fp16_inference():
    from hf_model_panel import VRAMCalculator, QuantMode, ComputeMode
    calc = VRAMCalculator()
    result = calc.estimate("meta-llama/Meta-Llama-3-8B", quant_mode=QuantMode.FP16, compute_mode=ComputeMode.INFERENCE)
    assert result.model_id == "meta-llama/Meta-Llama-3-8B"
    assert result.param_count_b == 8.0
    assert result.vram_required_gb > 0
    # FP16 inference: 8B * 2 bytes * 1.2 overhead = 19.2 GB
    assert result.vram_required_gb == pytest.approx(19.2, abs=1)


def test_vram_estimate_int4_inference():
    from hf_model_panel import VRAMCalculator, QuantMode, ComputeMode
    calc = VRAMCalculator()
    result = calc.estimate("meta-llama/Meta-Llama-3-8B", quant_mode=QuantMode.INT4, compute_mode=ComputeMode.INFERENCE)
    # INT4: 8B * 0.5 bytes * 1.2 = 4.8 GB
    assert result.vram_required_gb == pytest.approx(4.8, abs=1)


def test_vram_estimate_full_finetune():
    from hf_model_panel import VRAMCalculator, QuantMode, ComputeMode
    calc = VRAMCalculator()
    result = calc.estimate("mistralai/Mistral-7B-Instruct-v0.3", quant_mode=QuantMode.FP16, compute_mode=ComputeMode.FULL_FINE_TUNE)
    # Full FT: 7B * 2 * 4.0 = 56 GB
    assert result.vram_required_gb == pytest.approx(56.0, abs=5)


def test_vram_estimate_lora_finetune():
    from hf_model_panel import VRAMCalculator, QuantMode, ComputeMode
    calc = VRAMCalculator()
    result = calc.estimate("mistralai/Mistral-7B-Instruct-v0.3", quant_mode=QuantMode.FP16, compute_mode=ComputeMode.LORA_FINE_TUNE)
    # LoRA: 7B * 2 * 1.8 = 25.2 GB
    assert result.vram_required_gb == pytest.approx(25.2, abs=3)


def test_vram_gpu_compatibility():
    from hf_model_panel import VRAMCalculator, QuantMode, ComputeMode
    calc = VRAMCalculator()
    result = calc.estimate("meta-llama/Meta-Llama-3-8B", quant_mode=QuantMode.FP16, compute_mode=ComputeMode.INFERENCE)
    # 19.2 GB fits in A10G (24GB) but not T4 (16GB)
    assert result.fits_in_gpu["A10G"] is True
    assert result.fits_in_gpu["T4"] is False


def test_vram_recommended_gpus():
    from hf_model_panel import VRAMCalculator
    calc = VRAMCalculator()
    result = calc.estimate("meta-llama/Meta-Llama-3-8B")
    assert len(result.recommended_gpus) > 0
    # Debe estar ordenado por costo
    costs = [g["cost_per_hour"] for g in result.recommended_gpus]
    assert costs == sorted(costs)


def test_vram_estimate_all_modes():
    from hf_model_panel import VRAMCalculator
    calc = VRAMCalculator()
    results = calc.estimate_all_modes("meta-llama/Meta-Llama-3-8B")
    assert "fp16_inference" in results
    assert "int4_inference" in results
    assert "fp16_lora_finetune" in results
    assert "fp16_full_finetune" in results
    assert len(results) == 12  # 4 quant * 3 compute


def test_vram_unknown_model():
    from hf_model_panel import VRAMCalculator
    calc = VRAMCalculator()
    result = calc.estimate("unknown/model")
    assert result.param_count_b == 7.0  # default


def test_vram_cost_per_hour():
    from hf_model_panel import VRAMCalculator
    calc = VRAMCalculator()
    result = calc.estimate("meta-llama/Meta-Llama-3-8B")
    assert result.cost_per_hour > 0


# ===========================================================================
# 2. Playground
# ===========================================================================

def test_playground_find_spaces():
    from hf_model_panel import PlaygroundFinder
    finder = PlaygroundFinder()
    spaces = finder.find_spaces("meta-llama/Meta-Llama-3-8B")
    assert len(spaces) >= 1
    assert any("huggingface.co" in s.space_url for s in spaces)


def test_playground_inference_widget():
    from hf_model_panel import PlaygroundFinder
    finder = PlaygroundFinder()
    spaces = finder.find_spaces("unknown/model")
    # Siempre incluye el widget de inferencia
    assert any(s.sdk == "widget" for s in spaces)


def test_playground_embed_url():
    from hf_model_panel import PlaygroundFinder
    finder = PlaygroundFinder()
    spaces = finder.find_spaces("meta-llama/Meta-Llama-3-8B")
    for s in spaces:
        assert "embed" in s.embed_url or "widget" in s.embed_url


def test_playground_iframe_html():
    from hf_model_panel import PlaygroundFinder
    finder = PlaygroundFinder()
    playground = finder.get_playground("meta-llama/Meta-Llama-3-8B")
    assert "iframe" in playground["iframe_html"]


def test_playground_get_playground():
    from hf_model_panel import PlaygroundFinder
    finder = PlaygroundFinder()
    result = finder.get_playground("mistralai/Mistral-7B-Instruct-v0.3")
    assert "spaces" in result
    assert "model_id" in result


# ===========================================================================
# 3. License Analyzer
# ===========================================================================

def test_license_green_mit():
    from hf_model_panel import LicenseAnalyzer, LicenseCategory
    analyzer = LicenseAnalyzer()
    info = analyzer.analyze("MIT")
    assert info.category == LicenseCategory.GREEN
    assert info.commercial_use is True


def test_license_green_apache():
    from hf_model_panel import LicenseAnalyzer, LicenseCategory
    analyzer = LicenseAnalyzer()
    info = analyzer.analyze("Apache-2.0")
    assert info.category == LicenseCategory.GREEN


def test_license_yellow_llama():
    from hf_model_panel import LicenseAnalyzer, LicenseCategory
    analyzer = LicenseAnalyzer()
    info = analyzer.analyze("llama3")
    assert info.category == LicenseCategory.YELLOW
    assert info.commercial_use is True
    assert len(info.restrictions) > 0


def test_license_red_non_commercial():
    from hf_model_panel import LicenseAnalyzer, LicenseCategory
    analyzer = LicenseAnalyzer()
    info = analyzer.analyze("CC-BY-NC-4.0")
    assert info.category == LicenseCategory.RED
    assert info.commercial_use is False


def test_license_gated_model():
    from hf_model_panel import LicenseAnalyzer
    analyzer = LicenseAnalyzer()
    info = analyzer.analyze("llama3", gated=True, model_id="meta-llama/Meta-Llama-3-8B")
    assert info.gated is True
    assert "huggingface.co" in info.gated_message


def test_license_unknown():
    from hf_model_panel import LicenseAnalyzer, LicenseCategory
    analyzer = LicenseAnalyzer()
    info = analyzer.analyze("unknown-license-xyz")
    assert info.category == LicenseCategory.YELLOW  # precaución


def test_license_icon():
    from hf_model_panel import LicenseAnalyzer
    analyzer = LicenseAnalyzer()
    green = analyzer.analyze("MIT")
    assert green.to_dict()["icon"] == "🟢"
    red = analyzer.analyze("CC-BY-NC-4.0")
    assert red.to_dict()["icon"] == "🔴"


def test_license_summary():
    from hf_model_panel import LicenseAnalyzer
    analyzer = LicenseAnalyzer()
    info = analyzer.analyze("MIT")
    assert "Free commercial" in info.to_dict()["summary"]


# ===========================================================================
# 4. K8s Manifest Generator
# ===========================================================================

def test_k8s_vllm_deployment():
    from hf_model_panel import K8sManifestGenerator
    gen = K8sManifestGenerator()
    yaml = gen.generate_vllm_deployment("meta-llama/Meta-Llama-3-8B", gpu_type="A10G")
    assert "apiVersion: apps/v1" in yaml
    assert "kind: Deployment" in yaml
    assert "vllm" in yaml
    assert "meta-llama/Meta-Llama-3-8B" in yaml
    assert "nvidia.com/gpu" in yaml
    assert "kind: Service" in yaml


def test_k8s_tgi_deployment():
    from hf_model_panel import K8sManifestGenerator
    gen = K8sManifestGenerator()
    yaml = gen.generate_tgi_deployment("mistralai/Mistral-7B", gpu_type="A10G")
    assert "text-generation-inference" in yaml
    assert "mistralai/Mistral-7B" in yaml


def test_k8s_hpa():
    from hf_model_panel import K8sManifestGenerator
    gen = K8sManifestGenerator()
    yaml = gen.generate_hpa("meta-llama/Meta-Llama-3-8B", min_replicas=1, max_replicas=4)
    assert "HorizontalPodAutoscaler" in yaml
    assert "maxReplicas: 4" in yaml


def test_k8s_full_deploy():
    from hf_model_panel import K8sManifestGenerator
    gen = K8sManifestGenerator()
    result = gen.generate_full_deploy("meta-llama/Meta-Llama-3-8B", engine="vllm", gpu_type="A10G")
    assert "yaml" in result
    assert "filename" in result
    assert "kubectl apply" in result["apply_command"]
    assert "Deployment" in result["yaml"]


def test_k8s_full_deploy_tgi():
    from hf_model_panel import K8sManifestGenerator
    gen = K8sManifestGenerator()
    result = gen.generate_full_deploy("mistralai/Mistral-7B", engine="tgi")
    assert result["engine"] == "tgi"
    assert "text-generation-inference" in result["yaml"]


def test_k8s_secret_hf_token():
    from hf_model_panel import K8sManifestGenerator
    gen = K8sManifestGenerator()
    yaml = gen.generate_vllm_deployment("org/model")
    assert "HF_TOKEN" in yaml
    assert "Secret" in yaml
    assert "hf_YOUR_TOKEN_HERE" in yaml


# ===========================================================================
# 5. Benchmarks
# ===========================================================================

def test_benchmarks_get():
    from hf_model_panel import BenchmarkAnalyzer
    analyzer = BenchmarkAnalyzer()
    bench = analyzer.get_benchmarks("meta-llama/Meta-Llama-3-8B")
    assert bench.model_id == "meta-llama/Meta-Llama-3-8B"
    assert bench.tokens_per_second["A100-80"] == 120.0
    assert bench.weight_format == "safetensors"


def test_benchmarks_safetensors_flag():
    from hf_model_panel import BenchmarkAnalyzer
    analyzer = BenchmarkAnalyzer()
    bench = analyzer.get_benchmarks("meta-llama/Meta-Llama-3-8B")
    data = bench.to_dict()
    assert data["safetensors"] is True
    assert "immune" in data["safetensors_note"]


def test_benchmarks_domain_metrics():
    from hf_model_panel import BenchmarkAnalyzer
    analyzer = BenchmarkAnalyzer()
    bench = analyzer.get_benchmarks("meta-llama/Meta-Llama-3-8B")
    assert "MMLU" in bench.domain_metrics
    assert "finance" in bench.domain_metrics


def test_benchmarks_unknown_model():
    from hf_model_panel import BenchmarkAnalyzer
    analyzer = BenchmarkAnalyzer()
    bench = analyzer.get_benchmarks("unknown/model")
    assert bench.benchmark_source == "estimated"


def test_benchmarks_compare():
    from hf_model_panel import BenchmarkAnalyzer
    analyzer = BenchmarkAnalyzer()
    result = analyzer.compare_benchmarks([
        "meta-llama/Meta-Llama-3-8B",
        "mistralai/Mistral-7B-Instruct-v0.3",
    ])
    assert "comparison" in result
    assert len(result["comparison"]) == 2
    assert "best_tokens_per_sec" in result


# ===========================================================================
# 6. Lineage
# ===========================================================================

def test_lineage_base_model():
    from hf_model_panel import LineageTracker
    tracker = LineageTracker()
    result = tracker.get_lineage("meta-llama/Meta-Llama-3-8B")
    assert result["is_base_model"] is True
    assert result["parent_model"] == ""


def test_lineage_instruct():
    from hf_model_panel import LineageTracker
    tracker = LineageTracker()
    result = tracker.get_lineage("meta-llama/Meta-Llama-3-8B-Instruct")
    assert result["is_instruct"] is True
    assert result["parent_model"] == "meta-llama/Meta-Llama-3-8B"


def test_lineage_derivatives():
    from hf_model_panel import LineageTracker
    tracker = LineageTracker()
    result = tracker.get_lineage("meta-llama/Meta-Llama-3-8B")
    assert "meta-llama/Meta-Llama-3-8B-Instruct" in result["derivatives"]


def test_lineage_register_derivation():
    from hf_model_panel import LineageTracker
    tracker = LineageTracker()
    node = tracker.register_derivation(
        model_id="user/my-finetuned",
        parent_model="meta-llama/Meta-Llama-3-8B",
        dataset_id="org/dataset",
        dataset_revision="v1.0",
        training_params={"epochs": 3, "lr": 2e-4},
        k8s_config={"gpu": "A10G", "replicas": 2},
        author="test_user",
    )
    assert node.model_id == "user/my-finetuned"
    assert node.parent_model == "meta-llama/Meta-Llama-3-8B"
    # Verificar que aparece como derivado
    result = tracker.get_lineage("meta-llama/Meta-Llama-3-8B")
    assert "user/my-finetuned" in result["derivatives"]


def test_lineage_training_history():
    from hf_model_panel import LineageTracker
    tracker = LineageTracker()
    tracker.register_derivation(
        model_id="user/model-v2",
        parent_model="org/base",
        dataset_id="ds",
        training_params={"epochs": 5},
    )
    history = tracker.get_training_history("user/model-v2")
    assert history["has_history"] is True
    assert len(history["history"]) == 1


def test_lineage_no_history():
    from hf_model_panel import LineageTracker
    tracker = LineageTracker()
    history = tracker.get_training_history("meta-llama/Meta-Llama-3-8B")
    assert history["has_history"] is False


# ===========================================================================
# 7. ModelPanel integrado
# ===========================================================================

def test_model_panel_full():
    from hf_model_panel import ModelPanel
    panel = ModelPanel()
    result = panel.get_model_card_panel(
        "meta-llama/Meta-Llama-3-8B", license_str="llama3", gated=True
    )
    assert "panel_sections" in result
    assert "1_vram_calculator" in result["panel_sections"]
    assert "2_playground" in result["panel_sections"]
    assert "3_license" in result["panel_sections"]
    assert "4_k8s_manifest" in result["panel_sections"]
    assert "5_benchmarks" in result["panel_sections"]
    assert "6_lineage" in result["panel_sections"]


def test_model_panel_summary():
    from hf_model_panel import ModelPanel
    panel = ModelPanel()
    result = panel.get_model_card_panel("meta-llama/Meta-Llama-3-8B", license_str="llama3")
    summary = result["summary"]
    assert "vram_inference_fp16" in summary
    assert "license_category" in summary
    assert "tokens_per_sec" in summary
    assert "safetensors" in summary
    assert "recommended_gpu" in summary


# ===========================================================================
# 8. API REST — Panel endpoints
# ===========================================================================

def test_api_panel_full(client):
    resp = client.get("/api/v1/panel/meta-llama/Meta-Llama-3-8B?license=llama3&gated=true")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "panel_sections" in data


def test_api_panel_vram(client):
    resp = client.get("/api/v1/panel/meta-llama/Meta-Llama-3-8B/vram")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "fp16_inference" in data


def test_api_panel_vram_estimate(client):
    resp = client.post("/api/v1/panel/meta-llama/Meta-Llama-3-8B/vram/estimate", json={
        "quant_mode": "int4", "compute_mode": "inference"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["quant_mode"] == "int4"


def test_api_panel_playground(client):
    resp = client.get("/api/v1/panel/meta-llama/Meta-Llama-3-8B/playground")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "spaces" in data


def test_api_panel_license(client):
    resp = client.get("/api/v1/panel/meta-llama/Meta-Llama-3-8B/license?license=llama3&gated=true")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["category"] == "yellow"
    assert data["gated"] is True


def test_api_panel_k8s(client):
    resp = client.get("/api/v1/panel/meta-llama/Meta-Llama-3-8B/k8s-manifest?engine=vllm&gpu=A10G")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "yaml" in data
    assert "kubectl apply" in data["apply_command"]


def test_api_panel_benchmarks(client):
    resp = client.get("/api/v1/panel/meta-llama/Meta-Llama-3-8B/benchmarks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "tokens_per_second" in data


def test_api_panel_benchmarks_compare(client):
    resp = client.post("/api/v1/panel/benchmarks/compare", json={
        "model_ids": ["meta-llama/Meta-Llama-3-8B", "mistralai/Mistral-7B-Instruct-v0.3"]
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "comparison" in data


def test_api_panel_lineage(client):
    resp = client.get("/api/v1/panel/meta-llama/Meta-Llama-3-8B/lineage")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_base_model"] is True


def test_api_panel_lineage_register(client):
    resp = client.post("/api/v1/panel/user/my-model/lineage/register", json={
        "parent_model": "meta-llama/Meta-Llama-3-8B",
        "dataset_id": "org/ds",
        "training_params": {"epochs": 3},
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["parent_model"] == "meta-llama/Meta-Llama-3-8B"


def test_api_panel_training_history(client):
    resp = client.get("/api/v1/panel/meta-llama/Meta-Llama-3-8B/training-history")
    assert resp.status_code == 200


def test_api_panel_no_auth(no_auth_client):
    resp = no_auth_client.get("/api/v1/panel/meta-llama/Meta-Llama-3-8B")
    assert resp.status_code == 401
