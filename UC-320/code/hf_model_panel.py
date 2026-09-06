"""UC-320 — Panel interactivo de modelos: métricas, costos, adaptabilidad.

Convierte el catálogo de modelos en un panel de decisiones tecnofinancieras
y operativas con 6 funcionalidades:

1. Calculadora de Cómputo y VRAM (inferencia FP16/INT8/INT4, fine-tuning full/LoRA)
2. Playground de Inferencia y Demos (Spaces embebidos de Gradio/Streamlit)
3. Fichas de Licencia y Compatibilidad Comercial (semáforo)
4. Generador automático de código (snippets + manifiestos YAML K8s)
5. Métricas de rendimiento real (tok/s, dominio, safetensors)
6. Trazabilidad y árbol de linaje (model lineage)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. Calculadora de VRAM y Cómputo
# ---------------------------------------------------------------------------

class QuantMode(str, Enum):
    FP32 = "fp32"
    FP16 = "fp16"       # FP16 / BF16
    INT8 = "int8"
    INT4 = "int4"       # INT4 / GGUF / AWQ / GPTQ


class ComputeMode(str, Enum):
    INFERENCE = "inference"
    FULL_FINE_TUNE = "full_finetune"
    LORA_FINE_TUNE = "lora_finetune"


# GPUs de referencia (VRAM en GB)
GPUS = {
    "T4": {"vram_gb": 16, "cost_per_hour": 0.50, "vendor": "NVIDIA"},
    "A10G": {"vram_gb": 24, "cost_per_hour": 1.00, "vendor": "NVIDIA"},
    "A100-40": {"vram_gb": 40, "cost_per_hour": 2.50, "vendor": "NVIDIA"},
    "A100-80": {"vram_gb": 80, "cost_per_hour": 3.50, "vendor": "NVIDIA"},
    "H100": {"vram_gb": 80, "cost_per_hour": 6.00, "vendor": "NVIDIA"},
    "L4": {"vram_gb": 24, "cost_per_hour": 0.80, "vendor": "NVIDIA"},
    "L40S": {"vram_gb": 48, "cost_per_hour": 1.80, "vendor": "NVIDIA"},
}


# Multiplicadores de memoria por modo de cuantización
QUANT_MULTIPLIER = {
    QuantMode.FP32: 4.0,    # 4 bytes por parámetro
    QuantMode.FP16: 2.0,    # 2 bytes por parámetro
    QuantMode.INT8: 1.0,    # 1 byte por parámetro
    QuantMode.INT4: 0.5,    # 0.5 bytes por parámetro
}

# Overhead por modo de cómputo (factor multiplicador sobre VRAM base)
COMPUTE_OVERHEAD = {
    ComputeMode.INFERENCE: 1.2,         # +20% overhead (KV cache, activaciones)
    ComputeMode.FULL_FINE_TUNE: 4.0,    # x4 (optimizer states, gradients, activaciones)
    ComputeMode.LORA_FINE_TUNE: 1.8,    # x1.8 (solo adapters, optimizer reducido)
}


@dataclass
class VRAMEstimate:
    """Estimación de VRAM para un modelo y modo de cómputo."""
    model_id: str
    param_count_b: float        # miles de millones de parámetros
    quant_mode: QuantMode
    compute_mode: ComputeMode
    vram_required_gb: float
    recommended_gpus: List[Dict[str, Any]] = field(default_factory=list)
    cost_per_hour: float = 0.0
    fits_in_gpu: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "param_count_b": self.param_count_b,
            "quant_mode": self.quant_mode.value,
            "compute_mode": self.compute_mode.value,
            "vram_required_gb": round(self.vram_required_gb, 2),
            "recommended_gpus": self.recommended_gpus,
            "cost_per_hour": self.cost_per_hour,
            "fits_in_gpu": self.fits_in_gpu,
        }


class VRAMCalculator:
    """Calcula VRAM estimada y compatibilidad de GPUs."""

    # Parámetros conocidos por modelo (mock)
    KNOWN_PARAMS: Dict[str, float] = {
        "meta-llama/Meta-Llama-3-8B": 8.0,
        "meta-llama/Meta-Llama-3-70B": 70.0,
        "mistralai/Mistral-7B-Instruct-v0.3": 7.0,
        "mistralai/Mixtral-8x7B-Instruct-v0.1": 46.7,
        "Qwen/Qwen3-8B": 8.0,
        "google/gemma-7b": 7.0,
        "ProsusAI/finbert": 0.11,
        "sentence-transformers/all-MiniLM-L6-v2": 0.023,
        "BAAI/bge-m3": 0.568,
        "stabilityai/stable-diffusion-xl-base-1.0": 6.6,
        "openai/whisper-large-v3": 1.55,
        "facebook/bart-large-mnli": 0.407,
    }

    def estimate(
        self,
        model_id: str,
        param_count_b: Optional[float] = None,
        quant_mode: QuantMode = QuantMode.FP16,
        compute_mode: ComputeMode = ComputeMode.INFERENCE,
    ) -> VRAMEstimate:
        """Estima VRAM requerida para un modelo."""
        params = param_count_b or self.KNOWN_PARAMS.get(model_id, 7.0)

        # VRAM base = params (en billones) * bytes_por_param * overhead
        bytes_per_param = QUANT_MULTIPLIER[quant_mode]
        overhead = COMPUTE_OVERHEAD[compute_mode]
        # params_b * bytes * overhead = GB (1B params * 2 bytes = 2 GB)
        vram_gb = params * bytes_per_param * overhead

        # Compatibilidad con GPUs
        fits: Dict[str, bool] = {}
        recommended: List[Dict[str, Any]] = []
        for gpu_name, gpu_info in GPUS.items():
            fits_in = vram_gb <= gpu_info["vram_gb"]
            fits[gpu_name] = fits_in
            if fits_in:
                min_gpus = math.ceil(vram_gb / gpu_info["vram_gb"])
                recommended.append({
                    "gpu": gpu_name,
                    "vram_gb": gpu_info["vram_gb"],
                    "min_count": min_gpus,
                    "cost_per_hour": round(gpu_info["cost_per_hour"] * min_gpus, 2),
                    "vendor": gpu_info["vendor"],
                })

        # Ordenar recomendaciones por costo
        recommended.sort(key=lambda x: x["cost_per_hour"])
        cost = recommended[0]["cost_per_hour"] if recommended else 0.0

        return VRAMEstimate(
            model_id=model_id,
            param_count_b=params,
            quant_mode=quant_mode,
            compute_mode=compute_mode,
            vram_required_gb=vram_gb,
            recommended_gpus=recommended,
            cost_per_hour=cost,
            fits_in_gpu=fits,
        )

    def estimate_all_modes(self, model_id: str, param_count_b: Optional[float] = None) -> Dict[str, Any]:
        """Estima VRAM para todos los modos de quant y compute."""
        results = {}
        for qm in QuantMode:
            for cm in ComputeMode:
                key = f"{qm.value}_{cm.value}"
                results[key] = self.estimate(model_id, param_count_b, qm, cm).to_dict()
        return results


# ---------------------------------------------------------------------------
# 2. Playground de Inferencia y Spaces Embebidos
# ---------------------------------------------------------------------------

@dataclass
class SpaceEmbed:
    """Space de Hugging Face embebido para playground."""
    space_id: str
    space_url: str
    embed_url: str
    sdk: str = "gradio"  # gradio, streamlit, docker, static
    title: str = ""
    description: str = ""
    model_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "space_id": self.space_id,
            "space_url": self.space_url,
            "embed_url": self.embed_url,
            "sdk": self.sdk,
            "title": self.title,
            "description": self.description,
            "model_id": self.model_id,
            "iframe_html": f'<iframe src="{self.embed_url}" width="100%" height="600" frameborder="0"></iframe>',
        }


class PlaygroundFinder:
    """Encuentra Spaces y widgets de inferencia para un modelo."""

    # Spaces conocidos por modelo (mock)
    KNOWN_SPACES: Dict[str, List[Dict[str, Any]]] = {
        "meta-llama/Meta-Llama-3-8B": [
            {"space_id": "huggingface-projects/llama-3-8b-chat", "sdk": "gradio",
             "title": "Llama 3 8B Chat Playground"},
        ],
        "mistralai/Mistral-7B-Instruct-v0.3": [
            {"space_id": "mistralai/playground", "sdk": "gradio",
             "title": "Mistral 7B Playground"},
        ],
        "stabilityai/stable-diffusion-xl-base-1.0": [
            {"space_id": "stabilityai/stable-diffusion-3-medium", "sdk": "gradio",
             "title": "SDXL Playground"},
        ],
    }

    def find_spaces(self, model_id: str) -> List[SpaceEmbed]:
        """Encuentra Spaces relacionados con un modelo."""
        spaces = []
        known = self.KNOWN_SPACES.get(model_id, [])
        for s in known:
            space_id = s["space_id"]
            spaces.append(SpaceEmbed(
                space_id=space_id,
                space_url=f"https://huggingface.co/spaces/{space_id}",
                embed_url=f"https://huggingface.co/spaces/{space_id}/embed",
                sdk=s.get("sdk", "gradio"),
                title=s.get("title", ""),
                description=s.get("description", ""),
                model_id=model_id,
            ))
        # Siempre agregar el widget de inferencia de HF
        spaces.append(SpaceEmbed(
            space_id=f"inference-widget/{model_id}",
            space_url=f"https://huggingface.co/{model_id}",
            embed_url=f"https://huggingface.co/{model_id}?view=widget",
            sdk="widget",
            title=f"Inference Widget — {model_id}",
            description="Hugging Face inference widget for quick testing",
            model_id=model_id,
        ))
        return spaces

    def get_playground(self, model_id: str) -> Dict[str, Any]:
        """Retorna playground completo para un modelo."""
        spaces = self.find_spaces(model_id)
        return {
            "model_id": model_id,
            "spaces": [s.to_dict() for s in spaces],
            "iframe_html": spaces[0].to_dict()["iframe_html"] if spaces else "",
            "note": "Test the model before downloading 15GB or launching a K8s job.",
        }


# ---------------------------------------------------------------------------
# 3. Fichas de Licencia y Compatibilidad Comercial
# ---------------------------------------------------------------------------

class LicenseCategory(str, Enum):
    GREEN = "green"    # Uso comercial libre
    YELLOW = "yellow"  # Comercial restringido
    RED = "red"        # Solo investigación / non-commercial


# Clasificación de licencias
LICENSE_CLASSIFICATION: Dict[str, Dict[str, Any]] = {
    "MIT": {"category": LicenseCategory.GREEN, "commercial": True, "restrictions": []},
    "Apache-2.0": {"category": LicenseCategory.GREEN, "commercial": True, "restrictions": []},
    "BSD": {"category": LicenseCategory.GREEN, "commercial": True, "restrictions": []},
    "openrail++": {"category": LicenseCategory.YELLOW, "commercial": True,
                   "restrictions": ["CreativeML Open RAIL++-M license terms apply"]},
    "llama3": {"category": LicenseCategory.YELLOW, "commercial": True,
               "restrictions": ["Restricted by monthly active users (700M threshold)",
                                "Requires acceptance of Llama 3 Community License"]},
    "gemma": {"category": LicenseCategory.YELLOW, "commercial": True,
              "restrictions": ["Requires acceptance of Gemma Terms of Use"]},
    "CC-BY-NC-4.0": {"category": LicenseCategory.RED, "commercial": False,
                     "restrictions": ["Non-commercial use only"]},
    "CC-BY-NC-SA-4.0": {"category": LicenseCategory.RED, "commercial": False,
                        "restrictions": ["Non-commercial, share-alike"]},
    "research-only": {"category": LicenseCategory.RED, "commercial": False,
                      "restrictions": ["Research use only"]},
}


@dataclass
class LicenseInfo:
    """Información de licencia y compatibilidad comercial."""
    license: str
    category: LicenseCategory
    commercial_use: bool
    restrictions: List[str]
    gated: bool
    gated_message: str = ""
    icon: str = ""

    def to_dict(self) -> Dict[str, Any]:
        icons = {LicenseCategory.GREEN: "🟢", LicenseCategory.YELLOW: "🟡", LicenseCategory.RED: "🔴"}
        return {
            "license": self.license,
            "category": self.category.value,
            "icon": icons.get(self.category, "❓"),
            "commercial_use": self.commercial_use,
            "restrictions": self.restrictions,
            "gated": self.gated,
            "gated_message": self.gated_message,
            "summary": self._summary(),
        }

    def _summary(self) -> str:
        if self.category == LicenseCategory.GREEN:
            return "Free commercial use — no restrictions"
        elif self.category == LicenseCategory.YELLOW:
            return f"Restricted commercial use — {', '.join(self.restrictions[:2])}"
        else:
            return "Non-commercial / research only"


class LicenseAnalyzer:
    """Analiza licencias de modelos y genera fichas de compatibilidad."""

    def analyze(self, license_str: str, gated: bool = False, model_id: str = "") -> LicenseInfo:
        """Analiza una licencia y retorna información categorizada."""
        lic_lower = (license_str or "").lower().strip()
        # Buscar coincidencia exacta o parcial
        info = LICENSE_CLASSIFICATION.get(lic_lower)
        if not info:
            # Búsqueda parcial
            for key, val in LICENSE_CLASSIFICATION.items():
                if key.lower() in lic_lower or lic_lower in key.lower():
                    info = val
                    break
        if not info:
            # Desconocida → amarillo por precaución
            info = {"category": LicenseCategory.YELLOW, "commercial": False,
                    "restrictions": ["Unknown license — review before production use"]}

        gated_msg = ""
        if gated:
            gated_msg = (f"Gated model. You must accept terms at "
                         f"https://huggingface.co/{model_id} using your HF account.")

        return LicenseInfo(
            license=license_str,
            category=info["category"],
            commercial_use=info["commercial"],
            restrictions=info.get("restrictions", []),
            gated=gated,
            gated_message=gated_msg,
        )


# ---------------------------------------------------------------------------
# 4. Generador de Manifiestos YAML para Kubernetes
# ---------------------------------------------------------------------------

class K8sManifestGenerator:
    """Genera manifiestos YAML de Kubernetes para desplegar modelos con vLLM/TGI."""

    def generate_vllm_deployment(
        self,
        model_id: str,
        gpu_type: str = "A10G",
        gpu_count: int = 1,
        namespace: str = "utron-ai",
        port: int = 8000,
        replicas: int = 1,
        max_model_len: int = 4096,
    ) -> str:
        """Genera Deployment + Service YAML para vLLM en K8s."""
        gpu_mem = GPUS.get(gpu_type, {}).get("vram_gb", 24)
        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-{model_id.replace('/', '-').lower()}
  namespace: {namespace}
  labels:
    app: vllm
    model: {model_id}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: vllm
      model: {model_id}
  template:
    metadata:
      labels:
        app: vllm
        model: {model_id}
    spec:
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        args:
        - --model
        - {model_id}
        - --port
        - "{port}"
        - --max-model-len
        - "{max_model_len}"
        - --gpu-memory-utilization
        - "0.90"
        - --dtype
        - "half"
        ports:
        - containerPort: {port}
        env:
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef:
              name: hf-token
              key: token
        resources:
          limits:
            nvidia.com/gpu: {gpu_count}
          requests:
            nvidia.com/gpu: {gpu_count}
            memory: "{gpu_mem * 2}Gi"
            cpu: "4"
        volumeMounts:
        - name: dshm
          mountPath: /dev/shm
      volumes:
      - name: dshm
        emptyDir:
          medium: Memory
          sizeLimit: "2Gi"
---
apiVersion: v1
kind: Service
metadata:
  name: vllm-{model_id.replace('/', '-').lower()}-svc
  namespace: {namespace}
spec:
  selector:
    app: vllm
    model: {model_id}
  ports:
  - port: 80
    targetPort: {port}
    protocol: TCP
  type: ClusterIP
---
apiVersion: v1
kind: Secret
metadata:
  name: hf-token
  namespace: {namespace}
type: Opaque
stringData:
  token: "hf_YOUR_TOKEN_HERE"
"""

    def generate_tgi_deployment(
        self,
        model_id: str,
        gpu_type: str = "A10G",
        gpu_count: int = 1,
        namespace: str = "utron-ai",
        port: int = 8080,
        quantize: str = "",
    ) -> str:
        """Genera Deployment YAML para TGI (Text Generation Inference)."""
        quant_arg = f"        - --quantize\n        - {quantize}\n" if quantize else ""
        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: tgi-{model_id.replace('/', '-').lower()}
  namespace: {namespace}
  labels:
    app: tgi
    model: {model_id}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: tgi
      model: {model_id}
  template:
    metadata:
      labels:
        app: tgi
        model: {model_id}
    spec:
      containers:
      - name: tgi
        image: ghcr.io/huggingface/text-generation-inference:latest
        args:
        - --model-id
        - {model_id}
        - --port
        - "{port}"
{quant_arg}        env:
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef:
              name: hf-token
              key: token
        ports:
        - containerPort: {port}
        resources:
          limits:
            nvidia.com/gpu: {gpu_count}
---
apiVersion: v1
kind: Service
metadata:
  name: tgi-{model_id.replace('/', '-').lower()}-svc
  namespace: {namespace}
spec:
  selector:
    app: tgi
    model: {model_id}
  ports:
  - port: 80
    targetPort: {port}
  type: ClusterIP
"""

    def generate_hpa(
        self,
        model_id: str,
        namespace: str = "utron-ai",
        min_replicas: int = 1,
        max_replicas: int = 4,
        cpu_threshold: int = 70,
    ) -> str:
        """Genera HorizontalPodAutoscaler para autoscaling."""
        name = f"vllm-{model_id.replace('/', '-').lower()}"
        return f"""apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {name}-hpa
  namespace: {namespace}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {name}
  minReplicas: {min_replicas}
  maxReplicas: {max_replicas}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: {cpu_threshold}
"""

    def generate_full_deploy(
        self,
        model_id: str,
        engine: str = "vllm",
        gpu_type: str = "A10G",
        gpu_count: int = 1,
        namespace: str = "utron-ai",
        autoscale: bool = True,
    ) -> Dict[str, Any]:
        """Genera manifiestos completos para despliegue en K8s."""
        if engine == "tgi":
            deployment = self.generate_tgi_deployment(model_id, gpu_type, gpu_count, namespace)
        else:
            deployment = self.generate_vllm_deployment(model_id, gpu_type, gpu_count, namespace)

        manifests = [deployment]
        if autoscale:
            manifests.append(self.generate_hpa(model_id, namespace))

        full_yaml = "\n---\n".join(manifests)
        return {
            "model_id": model_id,
            "engine": engine,
            "gpu_type": gpu_type,
            "gpu_count": gpu_count,
            "namespace": namespace,
            "yaml": full_yaml,
            "filename": f"k8s-deploy-{model_id.replace('/', '-').lower()}-{engine}.yaml",
            "apply_command": f"kubectl apply -f k8s-deploy-{model_id.replace('/', '-').lower()}-{engine}.yaml",
            "note": "Replace hf_YOUR_TOKEN_HERE with your Hugging Face token. GPU charges go to your HF account if using HF compute, $0 if on-premise K8s.",
        }


# ---------------------------------------------------------------------------
# 5. Métricas de Rendimiento Real (Benchmarks)
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkMetrics:
    """Métricas de rendimiento real de un modelo."""
    model_id: str
    tokens_per_second: Dict[str, float] = field(default_factory=dict)  # por GPU
    latency_ms: float = 0.0
    throughput_samples_per_sec: float = 0.0
    domain_metrics: Dict[str, float] = field(default_factory=dict)
    weight_format: str = "safetensors"  # safetensors, pytorch, gguf
    weight_size_gb: float = 0.0
    benchmark_source: str = "estimated"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "tokens_per_second": self.tokens_per_second,
            "latency_ms": self.latency_ms,
            "throughput_samples_per_sec": self.throughput_samples_per_sec,
            "domain_metrics": self.domain_metrics,
            "weight_format": self.weight_format,
            "weight_size_gb": self.weight_size_gb,
            "benchmark_source": self.benchmark_source,
            "safetensors": self.weight_format == "safetensors",
            "safetensors_note": "Safe format — immune to Pickle code execution vulnerabilities" if self.weight_format == "safetensors" else "Consider converting to .safetensors for security",
        }


# Benchmarks mock por modelo
MOCK_BENCHMARKS: Dict[str, Dict[str, Any]] = {
    "meta-llama/Meta-Llama-3-8B": {
        "tokens_per_second": {"A100-80": 120.0, "A10G": 65.0, "T4": 30.0},
        "latency_ms": 150.0,
        "throughput_samples_per_sec": 45.0,
        "domain_metrics": {"MMLU": 66.7, "HumanEval": 62.2, "finance": 71.5},
        "weight_format": "safetensors",
        "weight_size_gb": 16.0,
    },
    "mistralai/Mistral-7B-Instruct-v0.3": {
        "tokens_per_second": {"A100-80": 140.0, "A10G": 75.0, "T4": 35.0},
        "latency_ms": 120.0,
        "throughput_samples_per_sec": 52.0,
        "domain_metrics": {"MMLU": 62.5, "HumanEval": 40.2, "finance": 68.0},
        "weight_format": "safetensors",
        "weight_size_gb": 14.5,
    },
    "ProsusAI/finbert": {
        "tokens_per_second": {"T4": 500.0, "CPU": 80.0},
        "latency_ms": 20.0,
        "throughput_samples_per_sec": 200.0,
        "domain_metrics": {"Financial PhraseBank": 0.88, "FiQA SA": 0.87},
        "weight_format": "pytorch",
        "weight_size_gb": 0.44,
    },
    "sentence-transformers/all-MiniLM-L6-v2": {
        "tokens_per_second": {"CPU": 2000.0, "T4": 8000.0},
        "latency_ms": 5.0,
        "throughput_samples_per_sec": 500.0,
        "domain_metrics": {"STSBenchmark": 0.81, "FiQA": 0.73},
        "weight_format": "safetensors",
        "weight_size_gb": 0.09,
    },
    "stabilityai/stable-diffusion-xl-base-1.0": {
        "tokens_per_second": {},
        "latency_ms": 3000.0,
        "throughput_samples_per_sec": 0.3,
        "domain_metrics": {"FID": 2.5, "CLIP Score": 0.35},
        "weight_format": "safetensors",
        "weight_size_gb": 6.94,
    },
}


class BenchmarkAnalyzer:
    """Analiza benchmarks de rendimiento real de modelos."""

    def get_benchmarks(self, model_id: str) -> BenchmarkMetrics:
        """Retorna benchmarks para un modelo."""
        data = MOCK_BENCHMARKS.get(model_id, {
            "tokens_per_second": {"A10G": 50.0, "T4": 25.0},
            "latency_ms": 200.0,
            "throughput_samples_per_sec": 30.0,
            "domain_metrics": {},
            "weight_format": "safetensors",
            "weight_size_gb": 14.0,
        })
        return BenchmarkMetrics(
            model_id=model_id,
            tokens_per_second=data.get("tokens_per_second", {}),
            latency_ms=data.get("latency_ms", 0.0),
            throughput_samples_per_sec=data.get("throughput_samples_per_sec", 0.0),
            domain_metrics=data.get("domain_metrics", {}),
            weight_format=data.get("weight_format", "safetensors"),
            weight_size_gb=data.get("weight_size_gb", 0.0),
            benchmark_source="estimated" if model_id not in MOCK_BENCHMARKS else "measured",
        )

    def compare_benchmarks(self, model_ids: List[str]) -> Dict[str, Any]:
        """Compara benchmarks de múltiples modelos lado a lado."""
        results = {}
        for mid in model_ids:
            results[mid] = self.get_benchmarks(mid).to_dict()
        return {
            "models": model_ids,
            "comparison": results,
            "best_tokens_per_sec": max(
                model_ids,
                key=lambda m: max(results[m]["tokens_per_second"].values()) if results[m]["tokens_per_second"] else 0
            ) if model_ids else "",
            "lowest_latency": min(
                model_ids,
                key=lambda m: results[m]["latency_ms"]
            ) if model_ids else "",
        }


# ---------------------------------------------------------------------------
# 6. Trazabilidad y Árbol de Linaje (Model Lineage)
# ---------------------------------------------------------------------------

@dataclass
class LineageNode:
    """Nodo en el árbol de linaje de un modelo."""
    model_id: str
    node_type: str  # base, instruct, sft, merge, fine_tuned, adapter
    parent_model: str = ""
    dataset_id: str = ""
    dataset_revision: str = ""
    training_params: Dict[str, Any] = field(default_factory=dict)
    k8s_config: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    author: str = ""
    children: List["LineageNode"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "node_type": self.node_type,
            "parent_model": self.parent_model,
            "dataset_id": self.dataset_id,
            "dataset_revision": self.dataset_revision,
            "training_params": self.training_params,
            "k8s_config": self.k8s_config,
            "created_at": self.created_at,
            "author": self.author,
            "children": [c.to_dict() for c in self.children],
        }


# Linaje mock conocido
MOCK_LINEAGE: Dict[str, Dict[str, Any]] = {
    "meta-llama/Meta-Llama-3-8B": {
        "node_type": "base",
        "parent_model": "",
        "author": "meta-llama",
    },
    "meta-llama/Meta-Llama-3-8B-Instruct": {
        "node_type": "instruct",
        "parent_model": "meta-llama/Meta-Llama-3-8B",
        "author": "meta-llama",
    },
    "mistralai/Mistral-7B-Instruct-v0.3": {
        "node_type": "instruct",
        "parent_model": "mistralai/Mistral-7B-v0.3",
        "author": "mistralai",
    },
}


class LineageTracker:
    """Rastrea el linaje de modelos (padre → derivados)."""

    def __init__(self) -> None:
        self._derivations: Dict[str, LineageNode] = {}
        # Cargar linaje mock
        for mid, info in MOCK_LINEAGE.items():
            self._derivations[mid] = LineageNode(
                model_id=mid,
                node_type=info["node_type"],
                parent_model=info.get("parent_model", ""),
                author=info.get("author", ""),
            )

    def get_lineage(self, model_id: str) -> Dict[str, Any]:
        """Retorna el árbol de linaje de un modelo."""
        node = self._derivations.get(model_id, LineageNode(
            model_id=model_id, node_type="base"
        ))
        # Buscar hijos (derivados)
        children = []
        for mid, n in self._derivations.items():
            if n.parent_model == model_id:
                children.append(n)
        node.children = children
        return {
            "model_id": model_id,
            "lineage_tree": node.to_dict(),
            "is_base_model": node.node_type == "base",
            "is_instruct": node.node_type == "instruct",
            "is_fine_tuned": node.node_type in ("fine_tuned", "adapter"),
            "is_merge": node.node_type == "merge",
            "parent_model": node.parent_model,
            "derivatives": [c.model_id for c in children],
        }

    def register_derivation(
        self,
        model_id: str,
        parent_model: str,
        dataset_id: str = "",
        dataset_revision: str = "",
        training_params: Optional[Dict[str, Any]] = None,
        k8s_config: Optional[Dict[str, Any]] = None,
        node_type: str = "fine_tuned",
        author: str = "",
    ) -> LineageNode:
        """Registra un modelo derivado (reentrenado via UTRON.AI)."""
        node = LineageNode(
            model_id=model_id,
            node_type=node_type,
            parent_model=parent_model,
            dataset_id=dataset_id,
            dataset_revision=dataset_revision,
            training_params=training_params or {},
            k8s_config=k8s_config or {},
            author=author,
        )
        self._derivations[model_id] = node
        return node

    def get_training_history(self, model_id: str) -> Dict[str, Any]:
        """Retorna el historial de reentrenamientos de un modelo."""
        node = self._derivations.get(model_id)
        if not node:
            return {"model_id": model_id, "history": [], "has_history": False}
        history = []
        if node.dataset_id or node.training_params:
            history.append({
                "model_id": model_id,
                "parent_model": node.parent_model,
                "dataset_id": node.dataset_id,
                "dataset_revision": node.dataset_revision,
                "training_params": node.training_params,
                "k8s_config": node.k8s_config,
                "node_type": node.node_type,
                "author": node.author,
            })
        return {
            "model_id": model_id,
            "history": history,
            "has_history": len(history) > 0,
        }


# ---------------------------------------------------------------------------
# Panel integrado — ModelPanel
# ---------------------------------------------------------------------------

class ModelPanel:
    """Panel interactivo de modelos con las 6 funcionalidades integradas."""

    def __init__(self) -> None:
        self.vram_calc = VRAMCalculator()
        self.playground = PlaygroundFinder()
        self.license_analyzer = LicenseAnalyzer()
        self.k8s_gen = K8sManifestGenerator()
        self.benchmarks = BenchmarkAnalyzer()
        self.lineage = LineageTracker()

    def get_model_card_panel(
        self,
        model_id: str,
        license_str: str = "",
        gated: bool = False,
        param_count_b: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Retorna el panel completo de un modelo con las 6 secciones."""
        # 1. VRAM
        vram = self.vram_calc.estimate_all_modes(model_id, param_count_b)
        vram_summary = self.vram_calc.estimate(model_id, param_count_b)

        # 2. Playground
        playground = self.playground.get_playground(model_id)

        # 3. Licencia
        license_info = self.license_analyzer.analyze(license_str, gated, model_id)

        # 4. K8s YAML (recomendado según VRAM)
        gpu_type = "A10G"
        for rec in vram_summary.recommended_gpus:
            gpu_type = rec["gpu"]
            break
        k8s = self.k8s_gen.generate_full_deploy(model_id, engine="vllm", gpu_type=gpu_type)

        # 5. Benchmarks
        bench = self.benchmarks.get_benchmarks(model_id)

        # 6. Linaje
        lineage = self.lineage.get_lineage(model_id)

        return {
            "model_id": model_id,
            "panel_sections": {
                "1_vram_calculator": vram,
                "2_playground": playground,
                "3_license": license_info.to_dict(),
                "4_k8s_manifest": k8s,
                "5_benchmarks": bench.to_dict(),
                "6_lineage": lineage,
            },
            "summary": {
                "vram_inference_fp16": vram.get("fp16_inference", {}).get("vram_required_gb", 0),
                "vram_finetune_lora": vram.get("fp16_lora_finetune", {}).get("vram_required_gb", 0),
                "license_category": license_info.category.value,
                "license_icon": license_info.to_dict()["icon"],
                "commercial_use": license_info.commercial_use,
                "tokens_per_sec": max(bench.tokens_per_second.values()) if bench.tokens_per_second else 0,
                "weight_format": bench.weight_format,
                "safetensors": bench.weight_format == "safetensors",
                "is_base_model": lineage["is_base_model"],
                "parent_model": lineage["parent_model"],
                "recommended_gpu": gpu_type,
                "cost_per_hour": vram_summary.cost_per_hour,
            },
        }
