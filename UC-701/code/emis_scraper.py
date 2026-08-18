"""UC-701 — Scraper de perfiles financieros desde EMIS.

Este módulo permite buscar una empresa por nombre y extraer sus KPIs financieros
clave publicados en emis.com.  Los datos se normalizan al formato esperado por
`core.analizar_empresa` y `forecasting.predecir`.

Dependencias adicionales:
    pip install requests beautifulsoup4
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from core import canonizar_indicador


EMIS_BASE = "https://www.emis.com"
EMIS_SEARCH = "/php/company-profile/index/search"
EMIS_PROFILE = "/php/company-profile"


class EmisScraperError(Exception):
    """Error controlado durante el scraping de EMIS."""
    pass


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })
    return session


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\n", " ").replace("\t", " ")).strip()


def search_company(name: str, country: Optional[str] = None, session: Optional[requests.Session] = None) -> Optional[str]:
    """Busca una empresa en EMIS y retorna la URL de su perfil.

    Si `country` se suministra, se prefieren resultados cuyo href contenga
    `company-profile/{country}/`.
    """
    sess = session or _session()
    payload = {"keyword": name, "rpp": 20, "sort": "relevance"}

    try:
        resp = sess.post(urljoin(EMIS_BASE, EMIS_SEARCH), data=payload, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise EmisScraperError(f"Error al contactar EMIS search: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")
    links: List[Dict[str, Any]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if EMIS_PROFILE in href and "/main.html" not in href and "/page" not in href and "/index/" not in href:
            text = _clean_text(a.get_text())
            links.append({"href": href, "text": text})

    if not links:
        return None

    # Filtrar por país si se pidió
    def _country_match(link: Dict[str, Any]) -> bool:
        if not country:
            return True
        return f"/company-profile/{country.upper()}/" in link["href"]

    candidates = [l for l in links if _country_match(l)]
    if not candidates:
        candidates = links  # fallback a cualquier país

    # Elegir el resultado con mayor similitud de nombre.
    # Si hay empate, preferir version en español (_es_) por compatibilidad con aliases.
    name_norm = re.sub(r"[^a-zA-Z0-9]", "", name).lower()

    def _score(link: Dict[str, Any]) -> tuple:
        sim = _name_similarity(name_norm, _clean_text(link["text"]).lower())
        is_spanish = "_es_" in link["href"].lower()
        return (sim, 1 if is_spanish else 0)

    best = max(candidates, key=_score)
    return urljoin(EMIS_BASE, best["href"])


def _name_similarity(query: str, candidate: str) -> float:
    candidate_norm = re.sub(r"[^a-zA-Z0-9]", "", candidate).lower()
    if not candidate_norm:
        return 0.0
    if query in candidate_norm or candidate_norm in query:
        return 1.0
    # Intersección de bigramas simple
    q = set(query)
    c = set(candidate_norm)
    inter = len(q & c)
    union = len(q | c)
    return inter / union if union else 0.0


def scrape_kpis(profile_url: str, session: Optional[requests.Session] = None) -> Dict[str, Any]:
    """Extrae los KPIs financieros clave de una URL de perfil EMIS."""
    sess = session or _session()
    try:
        resp = sess.get(profile_url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise EmisScraperError(f"Error al descargar perfil {profile_url}: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")

    company_name = _extract_company_name(soup) or "Empresa desconocida"
    country_code = _extract_country(profile_url)
    currency = _extract_currency(soup)

    indicadores: Dict[str, str] = {}
    for row in soup.find_all("div", class_="d-tr"):
        cells = row.find_all("div", class_="d-tc")
        if len(cells) < 2:
            continue
        label = _clean_text(cells[0].get_text())
        value = _clean_text(cells[1].get_text())
        canonico = canonizar_indicador(label)
        if canonico:
            indicadores[canonico] = value

    if not indicadores:
        # Fallback: parsear el bloque de texto conocido
        indicadores = _parse_fallback_text(soup)

    return {
        "empresa": company_name,
        "pais": country_code,
        "url": profile_url,
        "moneda": currency,
        "indicadores": indicadores,
    }


def _extract_company_name(soup: BeautifulSoup) -> Optional[str]:
    # El nombre aparece en h1 de la página
    h1 = soup.find("h1")
    if h1:
        return _clean_text(h1.get_text())
    return None


def _extract_country(profile_url: str) -> str:
    parts = urlparse(profile_url).path.split("/")
    for p in parts:
        if len(p) == 2 and p.isalpha():
            return p.upper()
    return "CO"


def _extract_currency(soup: BeautifulSoup) -> str:
    text = soup.get_text(" ")
    m = re.search(r"divisa local\s+([A-Z]{3})", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return "COP"


def _parse_fallback_text(soup: BeautifulSoup) -> Dict[str, str]:
    """Fallback por si el HTML cambia y no encuentra la tabla estructurada."""
    text = soup.get_text(" ")
    mapping = {
        "Ingresos netos por ventas": r"Ingresos netos por ventas\s+([-\d\.,]+(?:%|N/D))?",
        "Total Ingreso Operativo": r"Total Ingreso Operativo\s+([-\d\.,]+(?:%|N/D))?",
        "Ganancia operativa (EBIT)": r"Ganancia operativa \(EBIT\)\s+([-\d\.,]+(?:%|N/D))?",
        "Ganancia (Pérdida) Neta": r"Ganancia \(Pérdida\) Neta\s+([-\d\.,]+(?:%|N/D))?",
        "Activos Totales": r"Activos Totales\s+([-\d\.,]+(?:%|N/D))?",
        "Total de patrimonio": r"Total de patrimonio\s+([-\d\.,]+(?:%|N/D))?",
        "Margen Operacional": r"Margen Operacional\s+([-\d\.,]+(?:%|N/D))?",
        "Margen Neto": r"Margen Neto\s+([-\d\.,]+(?:%|N/D))?",
        "Rendimiento Sobre El Patrimonio (ROE)": r"Rendimiento Sobre El Patrimonio \(ROE\)\s+([-\d\.,]+(?:%|N/D))?",
        "Relación Deuda/Capital": r"Relación Deuda/Capital\s+([-\d\.,]+(?:%|N/D))?",
        "Prueba Ácida": r"Prueba Ácida\s+([-\d\.,]+(?:%|N/D))?",
        "Coeficiente De Efectivo": r"Coeficiente De Efectivo\s+([-\d\.,]+(?:%|N/D))?",
    }
    result = {}
    for canonico, pattern in mapping.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m and m.group(1):
            result[canonico] = m.group(1)
    return result


def scrape_company(name: str, country: Optional[str] = None) -> Dict[str, Any]:
    """Busca y scrapea una empresa en EMIS."""
    session = _session()
    profile_url = search_company(name, country=country, session=session)
    if not profile_url:
        raise EmisScraperError(f"No se encontró '{name}' en EMIS" + (f" para país {country}" if country else ""))
    time.sleep(0.5)
    return scrape_kpis(profile_url, session=session)


def to_analyze_payload(scrape_result: Dict[str, Any], fecha_corte: Optional[str] = None) -> Dict[str, Any]:
    """Convierte el resultado del scraper al payload de `core.analizar_empresa`."""
    from datetime import date
    fecha = fecha_corte or date.today().isoformat()
    return {
        "empresa": scrape_result["empresa"],
        "cortes": [
            {
                "fecha": fecha,
                "indicadores": scrape_result["indicadores"],
            }
        ],
    }


def scrape_multi_country(name: str, preferred_countries: Optional[List[str]] = None) -> Dict[str, Any]:
    """Intenta scrapear la empresa probando una lista de países preferidos.

    Si `preferred_countries` es None, busca global sin filtro.
    """
    if preferred_countries is None:
        return scrape_company(name)

    last_error: Optional[Exception] = None
    for country in preferred_countries:
        try:
            return scrape_company(name, country=country)
        except EmisScraperError as e:
            last_error = e
            continue
    raise last_error or EmisScraperError(f"No se encontró '{name}' en ningún país probado.")
