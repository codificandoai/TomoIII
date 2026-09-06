"""UC-320 — Generador de scripts y notebooks de fine-tuning (LoRA/PEFT).

Permite que el usuario elija un modelo y genere automáticamente un
script de ajuste fino apuntando al identificador del modelo en HF.

El script usa bibliotecas abiertas (transformers, peft, datasets, trl)
y descarga los pesos utilizando huggingface_hub sin intermediarios.

Los cargos de GPU van a la cuenta HF del usuario (token del usuario).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class FineTuneConfig:
    """Configuración para el script de fine-tuning."""
    base_model: str
    dataset_id: str
    output_dir: str = "./fine_tuned_model"
    method: str = "lora"  # lora, qlora, full
    task: str = "text-generation"  # text-generation, text-classification
    epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    max_seq_length: int = 512
    warmup_steps: int = 50
    save_steps: int = 500
    logging_steps: int = 10
    push_to_hub: bool = False
    hub_repo_id: str = ""
    use_gpu: bool = True
    fp16: bool = True
    bf16: bool = False
    gradient_checkpointing: bool = True
    optim: str = "paged_adamw_8bit"

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


class ScriptGenerator:
    """Genera scripts de fine-tuning LoRA/PEFT listos para ejecutar."""

    def generate_lora_script(self, config: FineTuneConfig) -> str:
        """Genera script Python completo de fine-tuning con LoRA."""
        push_section = ""
        if config.push_to_hub and config.hub_repo_id:
            push_section = f'''
# --- Push al Hub ---
trainer.push_to_hub("{config.hub_repo_id}")
print(f"Model pushed to https://huggingface.co/{config.hub_repo_id}")
'''

        target_modules = '["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]'

        return f'''"""
Fine-Tuning Script — generado por UTRON.AI UC-320
Modelo base: {config.base_model}
Dataset: {config.dataset_id}
Método: LoRA (PEFT)
"""
import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import (
    LoraConfig,
    get_peft_model,
    TaskType,
)

# --- Configuración ---
BASE_MODEL = "{config.base_model}"
DATASET_ID = "{config.dataset_id}"
OUTPUT_DIR = "{config.output_dir}"
# TOKEN = "hf_your_token"  # Requerido para modelos gated/privados

# --- Cargar tokenizer y modelo ---
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16 if {config.fp16} else torch.bfloat16 if {config.bf16} else torch.float32,
    device_map="auto",
    trust_remote_code=True,
)

# --- Configuración LoRA ---
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r={config.lora_r},
    lora_alpha={config.lora_alpha},
    lora_dropout={config.lora_dropout},
    bias="none",
    target_modules={target_modules},
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# --- Cargar y preparar dataset ---
dataset = load_dataset(DATASET_ID)

def tokenize_function(examples):
    return tokenizer(
        examples.get("text", examples.get("content", "")),
        truncation=True,
        max_length={config.max_seq_length},
        padding="max_length",
    )

tokenized = dataset.map(tokenize_function, batched=True)

data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=False,
)

# --- TrainingArguments ---
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs={config.epochs},
    per_device_train_batch_size={config.batch_size},
    gradient_accumulation_steps={config.gradient_accumulation_steps},
    learning_rate={config.learning_rate},
    warmup_steps={config.warmup_steps},
    save_steps={config.save_steps},
    logging_steps={config.logging_steps},
    fp16={config.fp16},
    bf16={config.bf16},
    gradient_checkpointing={config.gradient_checkpointing},
    optim="{config.optim}",
    save_total_limit=3,
    report_to="none",
    push_to_hub={config.push_to_hub},
    hub_model_id="{config.hub_repo_id}" if {config.push_to_hub} else None,
)

# --- Trainer ---
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized["train"],
    data_collator=data_collator,
)

# --- Entrenar ---
print("Starting fine-tuning...")
trainer.train()
print("Fine-tuning complete!")

# --- Guardar ---
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"Model saved to {{OUTPUT_DIR}}")
{push_section}
# --- Nota de billing ---
# Los cargos de GPU se debitan de tu cuenta de Hugging Face.
# UTRON.AI no paga por el cómputo.
'''

    def generate_qlora_script(self, config: FineTuneConfig) -> str:
        """Genera script QLoRA (quantization + LoRA) para GPU limitada."""
        config.method = "qlora"
        base = self.generate_lora_script(config)
        # Reemplazar la carga del modelo con quantización
        old_load = '''model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16 if {config.fp16} else torch.bfloat16 if {config.bf16} else torch.float32,
    device_map="auto",
    trust_remote_code=True,
)'''.format(config=config)
        new_load = '''from transformers import BitsAndBytesConfig

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)

model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
)'''
        return base.replace(old_load, new_load)

    def generate_classification_script(self, config: FineTuneConfig) -> str:
        """Genera script para fine-tuning de clasificación."""
        return f'''"""
Fine-Tuning Script — Clasificación
Modelo base: {config.base_model}
Dataset: {config.dataset_id}
"""
import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from peft import LoraConfig, get_peft_model, TaskType

tokenizer = AutoTokenizer.from_pretrained("{config.base_model}")
model = AutoModelForSequenceClassification.from_pretrained(
    "{config.base_model}",
    num_labels=2,
    torch_dtype=torch.float16,
    device_map="auto",
)

lora_config = LoraConfig(
    task_type=TaskType.SEQ_CLS,
    r={config.lora_r},
    lora_alpha={config.lora_alpha},
    lora_dropout={config.lora_dropout},
    target_modules=["query", "value"],
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

dataset = load_dataset("{config.dataset_id}")

def tokenize_fn(examples):
    return tokenizer(examples["text"], truncation=True, max_length={config.max_seq_length}, padding="max_length")

tokenized = dataset.map(tokenize_fn, batched=True)

training_args = TrainingArguments(
    output_dir="{config.output_dir}",
    num_train_epochs={config.epochs},
    per_device_train_batch_size={config.batch_size},
    learning_rate={config.learning_rate},
    fp16={config.fp16},
    save_steps={config.save_steps},
    logging_steps={config.logging_steps},
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized["train"],
    eval_dataset=tokenized.get("validation"),
)

trainer.train()
trainer.save_model("{config.output_dir}")
print("Classification model saved!")
'''

    def generate_notebook(self, config: FineTuneConfig) -> str:
        """Genera un Jupyter notebook en formato .ipynb como string JSON."""
        cells = [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    f"# Fine-Tuning: {config.base_model}\\n",
                    f"**Dataset:** {config.dataset_id}\\n",
                    f"**Método:** {config.method.upper()}\\n",
                    "\\n",
                    "Generado por UTRON.AI UC-320\\n",
                    "\\n",
                    "**Nota:** Los cargos de GPU se debitan de tu cuenta de Hugging Face.",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "!pip install transformers peft datasets accelerate bitsandbytes",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": self.generate_lora_script(config).split("\n"),
            },
        ]
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {"name": "python"},
            },
            "cells": cells,
        }
        import json
        return json.dumps(notebook, indent=2)

    def generate(self, config: FineTuneConfig) -> Dict[str, Any]:
        """Genera script + notebook según configuración."""
        if config.method == "qlora":
            script = self.generate_qlora_script(config)
        elif config.task == "text-classification":
            script = self.generate_classification_script(config)
        else:
            script = self.generate_lora_script(config)

        notebook = self.generate_notebook(config)

        return {
            "config": config.to_dict(),
            "script": script,
            "notebook": notebook,
            "filename": f"finetune_{config.base_model.replace('/', '_')}_{config.method}.py",
            "notebook_filename": f"finetune_{config.base_model.replace('/', '_')}_{config.method}.ipynb",
            "billing_note": "GPU charges go to your Hugging Face account, not UTRON.AI",
            "libraries": ["transformers", "peft", "datasets", "accelerate", "bitsandbytes"],
        }
