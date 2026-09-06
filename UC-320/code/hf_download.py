"""UC-320 — Acceso a pesos, archivos y datasets de Hugging Face.

Permite que los usuarios de UTRON.AI descarguen pesos (.bin, .safetensors)
o los carguen dinámicamente en sus entornos de ejecución.

Mecanismos:
  1. Descarga directa por HTTP:
     https://huggingface.co/USER/MODEL/resolve/main/model.safetensors
  2. Carga en código (Python):
     from transformers import AutoModelForCausalLM, AutoTokenizer
     tokenizer = AutoTokenizer.from_pretrained("org/model")
     model = AutoModelForCausalLM.from_pretrained("org/model")
  3. Carga con diffusers (para modelos de imagen):
     from diffusers import StableDiffusionPipeline
     pipe = StableDiffusionPipeline.from_pretrained("org/model")

Gestión de autenticación y límites de tasa:
  - Modelos/Datasets públicos: no requieren token.
  - Modelos privados o gated: requieren HF Access Token del usuario.
  - El token del usuario se pasa en el header Authorization: Bearer hf_xxx
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


HF_BASE = "https://huggingface.co"


@dataclass
class DownloadURL:
    """URL de descarga directa de un archivo del Hub."""
    repo_id: str
    filename: str
    revision: str = "main"
    url: str = ""

    def __post_init__(self) -> None:
        if not self.url:
            self.url = f"{HF_BASE}/{self.repo_id}/resolve/{self.revision}/{self.filename}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "filename": self.filename,
            "revision": self.revision,
            "url": self.url,
            "auth_required": False,  # Se actualiza según el repo
        }


@dataclass
class CodeSnippet:
    """Fragmento de código listo para copiar."""
    language: str  # python, javascript
    title: str
    code: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "title": self.title,
            "code": self.code,
            "description": self.description,
        }


class HFDownloadManager:
    """Gestión de descargas y carga de pesos desde Hugging Face.

    Genera URLs de descarga directa y snippets de código listos
    para que los usuarios carguen modelos en sus entornos.
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token

    def resolve_url(
        self, repo_id: str, filename: str, revision: str = "main",
    ) -> Dict[str, Any]:
        """Genera URL de descarga directa de un archivo.

        Estructura: https://huggingface.co/USER/MODEL/resolve/main/model.safetensors
        """
        dl = DownloadURL(repo_id=repo_id, filename=filename, revision=revision)
        result = dl.to_dict()
        # Si el repo es privado o gated, se requiere token
        result["auth_required"] = bool(self.token)
        if self.token:
            result["url_with_auth"] = (
                f"{dl.url}?download=true"
            )
            result["curl_command"] = (
                f'curl -L -H "Authorization: Bearer {self.token[:8]}..." '
                f'-o {filename} "{dl.url}"'
            )
        else:
            result["curl_command"] = f'curl -L -o {filename} "{dl.url}"'
        return result

    def list_files(self, repo_id: str, revision: str = "main") -> Dict[str, Any]:
        """Lista archivos disponibles en un repo (pesos, configs, tokenizers)."""
        # En producción: requests.get(f"{HF_BASE}/api/models/{repo_id}/tree/{revision}")
        # Mock: archivos típicos
        if "llama" in repo_id.lower():
            files = [
                "config.json", "tokenizer.json", "tokenizer_config.json",
                "model-00001-of-00004.safetensors", "model-00002-of-00004.safetensors",
                "model-00003-of-00004.safetensors", "model-00004-of-00004.safetensors",
                "model.safetensors.index.json", "special_tokens_map.json",
            ]
        elif "stable-diffusion" in repo_id.lower():
            files = [
                "config.json", "model_index.json", "vae/config.json",
                "unet/config.json", "scheduler/config.json",
                "text_encoder/config.json", "tokenizer/config.json",
                "vae/diffusion_pytorch_model.safetensors",
                "unet/diffusion_pytorch_model.safetensors",
                "text_encoder/model.safetensors",
            ]
        else:
            files = [
                "config.json", "pytorch_model.bin", "model.safetensors",
                "tokenizer.json", "tokenizer_config.json",
                "special_tokens_map.json", "vocab.txt",
            ]
        urls = [self.resolve_url(repo_id, f, revision) for f in files]
        return {
            "repo_id": repo_id,
            "revision": revision,
            "files": files,
            "download_urls": urls,
        }

    def generate_transformers_snippet(
        self, repo_id: str, task: str = "text-generation",
    ) -> CodeSnippet:
        """Genera snippet de código con transformers para cargar el modelo."""
        if task == "text-generation":
            code = f'''from transformers import AutoModelForCausalLM, AutoTokenizer

# Descarga los pesos directamente a la memoria o disco
tokenizer = AutoTokenizer.from_pretrained("{repo_id}")
model = AutoModelForCausalLM.from_pretrained("{repo_id}")

# Inferencia
inputs = tokenizer("Hello, world!", return_tensors="pt")
outputs = model.generate(**inputs, max_new_tokens=50)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
'''
        elif task == "feature-extraction" or task == "embeddings":
            code = f'''from transformers import AutoTokenizer, AutoModel
import torch

tokenizer = AutoTokenizer.from_pretrained("{repo_id}")
model = AutoModel.from_pretrained("{repo_id}")

# Generar embeddings
inputs = tokenizer("Text to embed", return_tensors="pt", padding=True, truncation=True)
with torch.no_grad():
    embeddings = model(**inputs).last_hidden_state.mean(dim=1)
print(embeddings.shape)
'''
        elif task == "text-classification" or task == "sentiment":
            code = f'''from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

tokenizer = AutoTokenizer.from_pretrained("{repo_id}")
model = AutoModelForSequenceClassification.from_pretrained("{repo_id}")

# Clasificación
inputs = tokenizer("Text to classify", return_tensors="pt")
with torch.no_grad():
    logits = model(**inputs).logits
    predicted_class = logits.argmax().item()
print(f"Predicted class: {{predicted_class}}")
'''
        else:
            code = f'''from transformers import AutoTokenizer, AutoModel

tokenizer = AutoTokenizer.from_pretrained("{repo_id}")
model = AutoModel.from_pretrained("{repo_id}")
print("Model loaded successfully")
'''
        return CodeSnippet(
            language="python",
            title=f"Load {repo_id} with transformers",
            code=code,
            description=f"Python snippet to load {repo_id} using the transformers library",
        )

    def generate_diffusers_snippet(self, repo_id: str) -> CodeSnippet:
        """Genera snippet de código con diffusers para modelos de imagen."""
        code = f'''from diffusers import StableDiffusionPipeline
import torch

# Cargar el modelo
pipe = StableDiffusionPipeline.from_pretrained(
    "{repo_id}",
    torch_dtype=torch.float16,
    use_safetensors=True,
)

# Mover a GPU si está disponible
pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")

# Generar imagen
image = pipe("A beautiful landscape").images[0]
image.save("output.png")
'''
        return CodeSnippet(
            language="python",
            title=f"Load {repo_id} with diffusers",
            code=code,
            description=f"Python snippet to load {repo_id} using the diffusers library",
        )

    def generate_datasets_snippet(self, dataset_id: str) -> CodeSnippet:
        """Genera snippet de código con datasets para cargar un dataset."""
        code = f'''from datasets import load_dataset

# Cargar dataset desde Hugging Face
dataset = load_dataset("{dataset_id}")

# Explorar
print(dataset)
print(dataset["train"][0])

# Streaming (para datasets grandes)
# dataset = load_dataset("{dataset_id}", streaming=True)
# for example in dataset["train"]:
#     print(example)
#     break
'''
        return CodeSnippet(
            language="python",
            title=f"Load dataset {dataset_id}",
            code=code,
            description=f"Python snippet to load {dataset_id} using the datasets library",
        )

    def generate_hf_hub_snippet(self, repo_id: str) -> CodeSnippet:
        """Genera snippet con huggingface_hub para descarga directa."""
        code = f'''from huggingface_hub import hf_hub_download, snapshot_download

# Descargar un archivo específico
file_path = hf_hub_download(
    repo_id="{repo_id}",
    filename="config.json",
    # token="hf_your_token"  # Requerido para repos privados/gated
)
print(f"Downloaded to: {{file_path}}")

# Descargar todo el repo (snapshot)
# snapshot = snapshot_download(repo_id="{repo_id}")
# print(f"Snapshot at: {{snapshot}}")
'''
        return CodeSnippet(
            language="python",
            title=f"Download {repo_id} with huggingface_hub",
            code=code,
            description="Use huggingface_hub to download weights without intermediaries",
        )

    def get_all_snippets(self, repo_id: str, task: str = "text-generation") -> List[CodeSnippet]:
        """Retorna todos los snippets relevantes para un repo."""
        snippets = [
            self.generate_hf_hub_snippet(repo_id),
            self.generate_transformers_snippet(repo_id, task),
        ]
        if task in ("text-to-image", "image-generation"):
            snippets.append(self.generate_diffusers_snippet(repo_id))
        return snippets

    def get_download_info(self, repo_id: str, revision: str = "main") -> Dict[str, Any]:
        """Información completa de descarga para un repo."""
        files_info = self.list_files(repo_id, revision)
        # Detectar task
        task = "text-generation"
        if "stable-diffusion" in repo_id.lower() or "sdxl" in repo_id.lower():
            task = "text-to-image"
        elif "bert" in repo_id.lower() or "sentiment" in repo_id.lower():
            task = "text-classification"
        elif "miniLM" in repo_id.lower() or "bge" in repo_id.lower() or "embed" in repo_id.lower():
            task = "feature-extraction"

        snippets = self.get_all_snippets(repo_id, task)
        return {
            "repo_id": repo_id,
            "revision": revision,
            "task": task,
            "files": files_info["files"],
            "download_urls": files_info["download_urls"],
            "code_snippets": [s.to_dict() for s in snippets],
            "auth_note": "Public repo: no token needed. Private/gated: use your HF token." if not self.token else "Using your HF token for private/gated access.",
        }
