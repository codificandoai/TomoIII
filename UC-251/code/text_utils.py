"""Utilidades de limpieza, normalización y detección de duplicados de texto."""
from __future__ import annotations

import hashlib
import re
from typing import List, Set


def normalize(text: str) -> str:
    """Normaliza espacios, quiebras de línea y acentos básicos."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    """Limpieza ligera: conserva estructura pero elimina basura Unicode."""
    text = text.replace("\x00", "")
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", text)
    return normalize(text)


def tokenize(text: str) -> List[str]:
    """Tokeniza alfanuméricos Unicode en minúsculas."""
    return re.findall(r"\w+", text.lower())


def tokens(text: str) -> Set[str]:
    return set(tokenize(text))


def sentence_split(text: str) -> List[str]:
    """División en oraciones básica."""
    sents = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sents if s.strip()]


def paragraph_split(text: str) -> List[str]:
    """Divide por líneas/párrafos en blanco."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def checksum_normalized(text: str) -> str:
    """Checksum del texto normalizado; útil para deduplicación exacta."""
    return sha256_text(normalize(text))


def approximate_duplicate(text_a: str, text_b: str, threshold: float = 0.92) -> bool:
    """Detecta duplicados aproximados mediante coeficiente de Jaccard."""
    ta = tokens(text_a)
    tb = tokens(text_b)
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    union = len(ta | tb)
    jaccard = inter / union if union else 0.0
    return jaccard >= threshold


def extract_headings(text: str) -> List[str]:
    """Extrae encabezados Markdown/HTML aproximados y líneas cortas en mayúsculas."""
    headings = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", "##", "###")):
            headings.append(re.sub(r"^#+\s*", "", stripped))
        elif re.match(r"<h[1-6][^>]*>", stripped, re.IGNORECASE):
            headings.append(re.sub(r"</?h[1-6][^>]*>", "", stripped, flags=re.IGNORECASE))
    return headings


def strip_markdown(text: str) -> str:
    """Elimina markup Markdown básico."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`{1,3}(.*?)`{1,3}", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    return text


def estimate_tokens(text: str, chars_per_token: int = 4) -> int:
    return max(1, len(text) // chars_per_token)
