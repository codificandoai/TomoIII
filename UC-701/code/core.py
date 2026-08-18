"""UC-701 — Core de análisis financiero multiempresa (COP).

Expone las funciones analizar_empresa, analizar_historial_empresa y
ejecutar_pipeline manteniendo compatibilidad con UC-701.md.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


try:
    from weasyprint import HTML
    WEASYPRINT_DISPONIBLE = True
except ImportError:  # pragma: no cover
    WEASYPRINT_DISPONIBLE = False


# -----------------------------------------------------------------------------
# Taxonomía de indicadores financieros.
# -----------------------------------------------------------------------------

INDICADORES = {
    "Ingresos netos por ventas": {
        "categoria": "Crecimiento", "unidad": "pct", "peso": 0.12,
        "aliases": ["ingresos netos por ventas", "ventas netas", "ventas", "ingresos por ventas"],
    },
    "Total Ingreso Operativo": {
        "categoria": "Crecimiento", "unidad": "pct", "peso": 0.10,
        "aliases": ["total ingreso operativo", "ingresos operativos", "ingreso operativo"],
    },
    "Ganancia operativa (EBIT)": {
        "categoria": "Rentabilidad", "unidad": "pct", "peso": 0.20,
        "aliases": ["ganancia operativa ebit", "ebit", "utilidad operativa"],
    },
    "Ganancia (Pérdida) Neta": {
        "categoria": "Rentabilidad", "unidad": "pct", "peso": 0.08,
        "aliases": ["ganancia perdida neta", "ganancia neta", "utilidad neta", "perdida neta"],
    },
    "Activos Totales": {
        "categoria": "Balance", "unidad": "pct", "peso": 0.06,
        "aliases": ["activos totales", "total activos"],
    },
    "Total de patrimonio": {
        "categoria": "Balance", "unidad": "pct", "peso": 0.14,
        "aliases": ["total de patrimonio", "patrimonio", "patrimonio total"],
    },
    "Margen Operacional": {
        "categoria": "Rentabilidad", "unidad": "pct", "peso": 0.08,
        "aliases": ["margen operacional", "margen operativo"],
    },
    "Margen Neto": {
        "categoria": "Rentabilidad", "unidad": "pct", "peso": 0.06,
        "aliases": ["margen neto"],
    },
    "Rendimiento Sobre El Patrimonio (ROE)": {
        "categoria": "Rentabilidad", "unidad": "pct", "peso": 0.06,
        "aliases": ["rendimiento sobre el patrimonio roe", "roe"],
    },
    "Relación Deuda/Capital": {
        "categoria": "Solvencia", "unidad": "pct", "peso": 0.08,
        "aliases": ["relacion deuda capital", "deuda capital", "debt to equity"],
    },
    "Prueba Ácida": {
        "categoria": "Liquidez", "unidad": "ratio", "peso": 0.10,
        "aliases": ["prueba acida", "quick ratio", "ratio acido"],
    },
    "Coeficiente de Efectivo": {
        "categoria": "Liquidez", "unidad": "ratio", "peso": 0.12,
        "aliases": ["coeficiente de efectivo", "cash ratio", "ratio de efectivo"],
    },
}

CATEGORIAS_ORDEN = ["Crecimiento", "Rentabilidad", "Balance", "Liquidez", "Solvencia"]


def normalizar_texto(valor: Any) -> str:
    """Normaliza texto para comparar nombres de columnas/indicadores."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-zA-Z0-9]+", " ", texto).strip().lower()
    return re.sub(r"\s+", " ", texto)


def canonizar_indicador(nombre: Any) -> Optional[str]:
    """Convierte variantes de nombre al indicador canónico o retorna None."""
    normalizado = normalizar_texto(nombre)
    for canonico, meta in INDICADORES.items():
        opciones = [canonico] + meta["aliases"]
        if normalizado in {normalizar_texto(x) for x in opciones}:
            return canonico
    return None


def parsear_numero(valor: Any) -> float:
    """Parsea valores numéricos en formatos colombianos/internacionales y N/D."""
    if valor is None or pd.isna(valor):
        return np.nan
    if isinstance(valor, (int, float, np.number)):
        return float(valor)

    texto = str(valor).strip()
    if normalizar_texto(texto) in {"", "nd", "na", "n a", "no disponible", "none", "nan", "null", "-"}:
        return np.nan

    texto = texto.replace("COP", "").replace("$", "").replace("%", "").strip()
    negativo_parentesis = texto.startswith("(") and texto.endswith(")")
    texto = texto.strip("() ")
    texto = re.sub(r"[^0-9,.-]", "", texto)

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        if texto.count(",") == 1:
            texto = texto.replace(",", ".")
        else:
            texto = texto.replace(",", "")

    try:
        resultado = float(texto)
        return -abs(resultado) if negativo_parentesis else resultado
    except ValueError:
        return np.nan


def fmt_pct(valor: Any, decimales: int = 2) -> str:
    if pd.isna(valor):
        return "N/D"
    return f"{float(valor):,.{decimales}f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_ratio(valor: Any, decimales: int = 2) -> str:
    if pd.isna(valor):
        return "N/D"
    return f"{float(valor):,.{decimales}f}x".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_fecha(valor: Any) -> str:
    if pd.isna(valor):
        return "Sin fecha"
    return pd.Timestamp(valor).strftime("%Y-%m-%d")


def estado_score(score: Optional[float]) -> Tuple[str, str]:
    if score is None or pd.isna(score):
        return "Sin calificación", "gris"
    if score >= 75:
        return "Riesgo financiero muy alto", "rojo"
    if score >= 50:
        return "Riesgo financiero alto", "naranja"
    if score >= 25:
        return "Riesgo financiero moderado", "amarillo"
    return "Riesgo financiero bajo", "verde"


# -----------------------------------------------------------------------------
# Carga y estandarización de datos.
# -----------------------------------------------------------------------------

def leer_datos(ruta: str | Path, hoja: int | str = 0) -> pd.DataFrame:
    """Lee CSV/XLSX/XLS y retorna estructura larga normalizada."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {ruta}")

    extension = ruta.suffix.lower()
    if extension == ".csv":
        try:
            bruto = pd.read_csv(ruta, sep=None, engine="python")
        except UnicodeDecodeError:
            bruto = pd.read_csv(ruta, sep=None, engine="python", encoding="latin-1")
    elif extension in {".xlsx", ".xls", ".xlsm"}:
        bruto = pd.read_excel(ruta, sheet_name=hoja)
    else:
        raise ValueError("Formato no soportado. Use CSV, XLS, XLSX o XLSM.")

    return estandarizar_datos(bruto)


def estandarizar_datos(bruto: pd.DataFrame) -> pd.DataFrame:
    """Estandariza DataFrame largo o ancho al esquema analítico."""
    if bruto.empty:
        raise ValueError("El archivo no contiene filas de datos.")

    original = bruto.copy()
    mapa_columnas = {col: normalizar_texto(col) for col in original.columns}

    col_empresa = next((c for c, n in mapa_columnas.items() if n in {"empresa", "compania", "compañia", "company", "razon social", "razon_social"}), None)
    col_fecha = next((c for c, n in mapa_columnas.items() if n in {"fecha", "date", "periodo", "period", "corte", "fecha corte"}), None)
    col_indicador = next((c for c, n in mapa_columnas.items() if n in {"indicador", "metric", "metrica", "métrica", "cuenta"}), None)
    col_valor = next((c for c, n in mapa_columnas.items() if n in {"valor", "value", "dato", "resultado"}), None)
    col_unidad = next((c for c, n in mapa_columnas.items() if n in {"unidad", "unit", "tipo unidad", "tipo"}), None)

    if col_indicador is not None and col_valor is not None:
        largo = pd.DataFrame({
            "empresa": original[col_empresa] if col_empresa else "Empresa sin nombre",
            "fecha": original[col_fecha] if col_fecha else pd.NaT,
            "indicador_original": original[col_indicador],
            "valor": original[col_valor],
            "unidad": original[col_unidad] if col_unidad else None,
        })
    else:
        columnas_indicador = {
            col: canonizar_indicador(col)
            for col in original.columns
            if canonizar_indicador(col) is not None
        }
        if not columnas_indicador:
            disponibles = ", ".join(map(str, original.columns))
            raise ValueError(f"No se detectaron indicadores financieros. Columnas encontradas: {disponibles}")

        id_vars = [c for c in [col_empresa, col_fecha] if c is not None]
        largo = original.melt(
            id_vars=id_vars,
            value_vars=list(columnas_indicador.keys()),
            var_name="indicador_original",
            value_name="valor",
        )
        largo["empresa"] = largo[col_empresa] if col_empresa else "Empresa sin nombre"
        largo["fecha"] = largo[col_fecha] if col_fecha else pd.NaT
        largo["unidad"] = None
        largo = largo[["empresa", "fecha", "indicador_original", "valor", "unidad"]]

    largo["empresa"] = largo["empresa"].fillna("Empresa sin nombre").astype(str).str.strip()
    largo["fecha"] = pd.to_datetime(largo["fecha"], errors="coerce")
    largo["indicador"] = largo["indicador_original"].apply(canonizar_indicador)
    largo["valor"] = largo["valor"].apply(parsear_numero)
    largo["unidad"] = largo.apply(
        lambda r: INDICADORES[r["indicador"]]["unidad"] if r["indicador"] in INDICADORES else r["unidad"],
        axis=1,
    )

    largo = largo[largo["indicador"].notna()].copy()
    if largo.empty:
        raise ValueError("No quedaron registros válidos después de normalizar indicadores.")

    largo = largo.sort_values(["empresa", "fecha", "indicador"], na_position="last")
    largo = (
        largo.groupby(["empresa", "fecha", "indicador"], as_index=False, dropna=False)
        .agg(valor=("valor", lambda x: x.dropna().iloc[-1] if x.notna().any() else np.nan), unidad=("unidad", "last"))
    )
    return largo.sort_values(["empresa", "fecha", "indicador"], na_position="last").reset_index(drop=True)


# -----------------------------------------------------------------------------
# Diagnóstico, scoring y tendencias.
# -----------------------------------------------------------------------------

def calcular_riesgo_indicador(indicador: str, valor: float) -> Tuple[float, str, str, str]:
    """Retorna riesgo 0-100, estado, severidad y explicación por indicador."""
    if pd.isna(valor):
        return 50.0, "Datos insuficientes", "info", "No hay dato disponible; se aplica riesgo de incertidumbre intermedia."

    if indicador in {"Ingresos netos por ventas", "Total Ingreso Operativo"}:
        if valor < -20:
            return min(100, 50 - valor), "Contracción severa", "critico", "Caída superior al 20%: contracción grave del núcleo del negocio."
        if valor < 0:
            return min(100, 50 - valor), "Contracción moderada", "alerta", "Disminución de ingresos que exige revisar demanda, precios, clientes y canales."
        if valor < 5:
            return 35.0, "Estancamiento o crecimiento débil", "info", "Crecimiento positivo, pero limitado."
        return 15.0, "Crecimiento saludable", "ok", "Expansión positiva de ingresos."

    if indicador == "Ganancia operativa (EBIT)":
        if valor < -50:
            return 100.0, "Colapso de rentabilidad operativa", "critico", "Deterioro extremo del EBIT; la operación requiere intervención prioritaria."
        if valor < 0:
            return min(95, 50 - valor), "Pérdida operativa", "critico", "El resultado operativo se deteriora y sugiere incapacidad de cubrir la estructura de costos."
        if valor < 5:
            return 40.0, "Rentabilidad operativa débil", "alerta", "La mejora operativa es limitada o vulnerable."
        return 10.0, "Rentabilidad operativa favorable", "ok", "El EBIT evoluciona favorablemente."

    if indicador in {"Ganancia (Pérdida) Neta", "Margen Neto", "Rendimiento Sobre El Patrimonio (ROE)"}:
        if valor < -20:
            return min(100, 60 - valor), "Rentabilidad neta crítica", "critico", "El indicador neto/retorno presenta deterioro severo."
        if valor < 0:
            return min(90, 50 - valor), "Rentabilidad neta negativa", "alerta", "El indicador se encuentra en terreno negativo."
        if valor < 5:
            return 35.0, "Rentabilidad neta limitada", "info", "La rentabilidad/retorno positivo es bajo."
        return 15.0, "Rentabilidad neta favorable", "ok", "La rentabilidad/retorno evoluciona positivamente."

    if indicador == "Margen Operacional":
        if valor < -10:
            return min(100, 55 - valor), "Margen operacional negativo severo", "critico", "El margen operacional es negativo y refleja presión estructural de costos/precios."
        if valor < 0:
            return min(90, 50 - valor), "Margen operacional negativo", "alerta", "La operación no está generando margen positivo."
        if valor < 5:
            return 35.0, "Margen operacional estrecho", "info", "Existe baja holgura ante caídas de ventas o aumentos de costos."
        return 10.0, "Margen operacional favorable", "ok", "La operación mantiene margen positivo."

    if indicador == "Activos Totales":
        if valor < -20:
            return min(95, 50 - valor), "Reducción agresiva de activos", "alerta", "La base de activos cae más de 20%; requiere explicar desinversión, deterioro o contracción."
        if valor < 0:
            return min(80, 45 - valor), "Reducción de activos", "info", "Los activos disminuyen; debe verificarse si la reducción mejora eficiencia o debilita capacidad operativa."
        return 20.0, "Activos estables o crecientes", "ok", "La base de activos se mantiene o aumenta."

    if indicador == "Total de patrimonio":
        if valor < -40:
            return 100.0, "Deterioro patrimonial grave", "critico", "Caída superior al 40%: menor capacidad de absorber pérdidas y mayor fragilidad financiera."
        if valor < 0:
            return min(95, 55 - valor), "Deterioro patrimonial", "alerta", "El patrimonio disminuye; pueden existir pérdidas acumuladas, distribuciones o ajustes contables."
        return 20.0, "Patrimonio estable o creciente", "ok", "El patrimonio se sostiene o crece."

    if indicador == "Prueba Ácida":
        if valor < 0:
            return 100.0, "Liquidez inmediata inválida/crítica", "critico", "Un ratio negativo debe validarse; de confirmarse, indica una posición de corto plazo extremadamente frágil."
        if valor < 0.5:
            return 100 - valor * 20, "Liquidez inmediata crítica", "critico", "La prueba ácida es inferior a 0,5x y no cubre razonablemente pasivos corrientes sin inventarios."
        if valor < 1.0:
            return 70 - (valor - 0.5) * 40, "Liquidez inmediata baja", "alerta", "La prueba ácida está por debajo de 1,0x; existe dependencia de inventarios, refinanciación o flujos futuros."
        return max(10, 30 - (valor - 1) * 10), "Liquidez inmediata adecuada", "ok", "La prueba ácida es igual o superior a 1,0x."

    if indicador == "Coeficiente de Efectivo":
        if valor < 0:
            return 95.0, "Posición de caja negativa", "critico", "El ratio negativo debe validarse; si es correcto, refleja tensión extrema de tesorería."
        if valor < 0.1:
            return 85.0, "Caja crítica", "critico", "La caja disponible cubre una proporción muy reducida de las obligaciones de corto plazo."
        if valor < 0.2:
            return 65.0, "Caja baja", "alerta", "La posición de efectivo es limitada frente a pasivos corrientes."
        return 25.0, "Caja adecuada", "ok", "La cobertura inmediata de efectivo es razonable."

    if indicador == "Relación Deuda/Capital":
        if valor > 100:
            return min(100, 70 + (valor - 100) * 0.2), "Apalancamiento muy alto", "critico", "La deuda supera al capital/patrimonio; aumenta la vulnerabilidad a refinanciación y tasas."
        if valor > 60:
            return 70.0, "Apalancamiento alto", "alerta", "La deuda representa una proporción elevada del capital."
        if valor > 40:
            return 50.0, "Apalancamiento moderado", "info", "La deuda/capital requiere monitoreo, especialmente si el patrimonio está disminuyendo."
        return 30.0, "Apalancamiento bajo o moderado", "ok", "La relación deuda/capital es contenida; debe interpretarse junto con la trayectoria patrimonial."

    return 50.0, "Sin regla", "info", "No existe una regla configurada para este indicador."


def diagnosticar_registro(indicador: str, valor: float, fecha: Any = None) -> Dict[str, Any]:
    riesgo, estado, severidad, mensaje = calcular_riesgo_indicador(indicador, valor)
    unidad = INDICADORES[indicador]["unidad"]
    return {
        "indicador": indicador,
        "fecha": fmt_fecha(fecha),
        "valor": None if pd.isna(valor) else float(valor),
        "unidad": unidad,
        "valor_formateado": fmt_ratio(valor) if unidad == "ratio" else fmt_pct(valor),
        "categoria": INDICADORES[indicador]["categoria"],
        "riesgo_individual": round(float(np.clip(riesgo, 0, 100)), 2),
        "estado": estado,
        "severidad": severidad,
        "mensaje": mensaje,
        "peso": INDICADORES[indicador]["peso"],
    }


def tendencia_indicador(serie: pd.DataFrame, indicador: str) -> str:
    """Evalúa dirección temporal si existen al menos dos observaciones válidas."""
    s = serie.dropna(subset=["valor"]).sort_values("fecha")
    if len(s) < 2:
        return "Sin historial suficiente"
    primero, ultimo = s.iloc[0]["valor"], s.iloc[-1]["valor"]
    delta = ultimo - primero
    if abs(delta) < 1e-9:
        return "Estable"

    if indicador == "Relación Deuda/Capital":
        return "Deteriorando" if delta > 0 else "Mejorando"
    if indicador in {"Prueba Ácida", "Coeficiente de Efectivo"}:
        return "Mejorando" if delta > 0 else "Deteriorando"
    return "Al alza" if delta > 0 else "A la baja"


def generar_recomendaciones(df_diag: pd.DataFrame, score: float) -> List[Dict[str, str]]:
    """Recomendaciones rule-based priorizadas."""
    valores = df_diag.set_index("indicador")["valor"].to_dict()
    recs = []

    if valores.get("Prueba Ácida", np.nan) < 0.5 or valores.get("Coeficiente de Efectivo", np.nan) < 0.1:
        recs.append({
            "prioridad": "P0", "frente": "Liquidez",
            "accion": "Implementar flujo de caja de 13 semanas, control diario de caja, aceleración de cobros y negociación de vencimientos con proveedores y acreedores.",
        })
    if valores.get("Ganancia operativa (EBIT)", np.nan) < 0 or valores.get("Margen Operacional", np.nan) < 0:
        recs.append({
            "prioridad": "P0", "frente": "Rentabilidad",
            "accion": "Separar costos fijos y variables, identificar líneas/clientes deficitarios, revisar precios, descuentos, productividad y gastos no esenciales.",
        })
    if valores.get("Total de patrimonio", np.nan) < -20:
        recs.append({
            "prioridad": "P1", "frente": "Patrimonio",
            "accion": "Conciliar pérdidas acumuladas, reservas, distribuciones y ajustes contables; evaluar capitalización, retención de utilidades o reestructuración según viabilidad.",
        })
    if valores.get("Ingresos netos por ventas", np.nan) < 0:
        recs.append({
            "prioridad": "P1", "frente": "Ingresos",
            "accion": "Analizar caída por cliente, canal, producto, precio y volumen; construir un plan comercial con metas de recuperación y sensibilidad de margen.",
        })
    if valores.get("Relación Deuda/Capital", np.nan) > 40:
        recs.append({
            "prioridad": "P1", "frente": "Deuda",
            "accion": "Mapear vencimientos, tasas, garantías, covenants y capacidad de servicio; evaluar refinanciación antes de eventos de incumplimiento.",
        })

    recs.append({
        "prioridad": "P2", "frente": "Gobierno de datos",
        "accion": "Completar utilidad/pérdida neta, margen neto, ROE, flujo de efectivo, cuentas por cobrar/pagar e intereses para un diagnóstico de solvencia más fiable.",
    })
    return recs


def construir_resumen(
    empresa: str,
    fecha: Any,
    df_diag: pd.DataFrame,
    score: float,
    cobertura: float,
    tendencias: Dict[str, str],
) -> Dict[str, Any]:
    """Construye salida textual rica, estructurada y útil para LLMs."""
    valores = df_diag.set_index("indicador")["valor"].to_dict()
    get = lambda n: valores.get(n, np.nan)
    ventas = get("Ingresos netos por ventas")
    ingreso_op = get("Total Ingreso Operativo")
    ebit = get("Ganancia operativa (EBIT)")
    margen_op = get("Margen Operacional")
    activos = get("Activos Totales")
    patrimonio = get("Total de patrimonio")
    prueba = get("Prueba Ácida")
    efectivo = get("Coeficiente de Efectivo")
    deuda_capital = get("Relación Deuda/Capital")

    nivel, _ = estado_score(score)
    criticos = df_diag[df_diag["severidad"] == "critico"]["indicador"].tolist()
    alertas_list = df_diag[df_diag["severidad"] == "alerta"]["indicador"].tolist()

    sintesis_componentes = []
    if not pd.isna(ventas):
        sintesis_componentes.append(f"ventas {fmt_pct(ventas)}")
    if not pd.isna(ebit):
        sintesis_componentes.append(f"EBIT {fmt_pct(ebit)}")
    if not pd.isna(patrimonio):
        sintesis_componentes.append(f"patrimonio {fmt_pct(patrimonio)}")
    if not pd.isna(prueba):
        sintesis_componentes.append(f"prueba ácida {fmt_ratio(prueba)}")

    sintesis = (
        f"{empresa} presenta un nivel de {nivel.lower()} al {fmt_fecha(fecha)} "
        f"(score {score:.1f}/100; cobertura de datos {cobertura:.0%}). "
        + ("Los principales indicadores disponibles son: " + ", ".join(sintesis_componentes) + "." if sintesis_componentes else "No hay indicadores suficientes para emitir una conclusión cuantitativa.")
    )

    secciones = []
    if not pd.isna(ventas) or not pd.isna(ingreso_op):
        secciones.append({
            "titulo": "Crecimiento y actividad operativa",
            "texto": (
                f"Los ingresos netos por ventas registran {fmt_pct(ventas)} y el ingreso operativo total {fmt_pct(ingreso_op)}. "
                "Cuando ambos indicadores caen de forma comparable, la señal es consistente con una contracción del núcleo comercial u operativo, no únicamente con una reclasificación contable aislada."
            )
        })
    if not pd.isna(ebit) or not pd.isna(margen_op):
        secciones.append({
            "titulo": "Rentabilidad operativa",
            "texto": (
                f"El EBIT muestra {fmt_pct(ebit)} y el margen operacional {fmt_pct(margen_op)}. "
                "Un margen operacional negativo junto con deterioro del EBIT indica presión sobre precios, volumen, mezcla comercial y/o costos, por lo que se debe validar la capacidad de la operación para sostenerse sin ajustes de estructura o financiación adicional."
            )
        })
    if not pd.isna(activos) or not pd.isna(patrimonio):
        secciones.append({
            "titulo": "Balance y absorción de pérdidas",
            "texto": (
                f"Los activos totales varían {fmt_pct(activos)} y el patrimonio {fmt_pct(patrimonio)}. "
                "Una caída del patrimonio más pronunciada que la de los activos reduce el colchón para absorber pérdidas y puede amplificar el apalancamiento económico, aun cuando la razón deuda/capital no parezca extrema de manera aislada."
            )
        })
    if not pd.isna(prueba) or not pd.isna(efectivo):
        secciones.append({
            "titulo": "Liquidez y tesorería",
            "texto": (
                f"La prueba ácida es {fmt_ratio(prueba)} y el coeficiente de efectivo es {fmt_ratio(efectivo)}. "
                "Una prueba ácida inferior a 1,0x implica que los activos líquidos, sin inventarios, no cubren totalmente las obligaciones corrientes; valores inferiores a 0,5x representan una señal crítica que exige gestión diaria de caja y vencimientos."
            )
        })
    if not pd.isna(deuda_capital):
        secciones.append({
            "titulo": "Estructura de capital y solvencia",
            "texto": (
                f"La relación deuda/capital es {fmt_pct(deuda_capital)}. "
                "Este ratio debe leerse junto con la tendencia del patrimonio: si el patrimonio se reduce, una deuda estable puede convertirse en una carga relativa mayor, disminuir la capacidad de absorción de pérdidas y limitar el acceso a nueva financiación."
            )
        })

    no_disponibles = df_diag[df_diag["valor"].isna()]["indicador"].tolist()
    limitaciones = []
    if no_disponibles:
        limitaciones.append("Indicadores no disponibles: " + ", ".join(no_disponibles) + ".")
    if cobertura < 0.75:
        limitaciones.append("La cobertura inferior a 75% reduce la confiabilidad del score; complete datos de utilidad neta, margen neto, ROE y estados financieros absolutos.")
    limitaciones.append("El diagnóstico no reemplaza auditoría, due diligence, análisis sectorial ni la revisión de notas a los estados financieros.")

    texto_plano = "\n\n".join([
        "Resumen del estado financiero de la empresa (COP)",
        sintesis,
        *[f"{s['titulo']}: {s['texto']}" for s in secciones],
        "Interpretación ejecutiva: " + (
            "La combinación de contracción de ingresos, deterioro operativo, debilitamiento patrimonial y/o restricción de liquidez eleva el riesgo de estrés de tesorería y exige medidas de estabilización." if score >= 50
            else "Los indicadores disponibles no reflejan un nivel crítico agregado, aunque deben monitorearse las alertas individuales y su tendencia."
        ),
        "Limitaciones: " + " ".join(limitaciones),
    ])

    return {
        "titulo": "Resumen del estado financiero de la empresa (COP)",
        "sintesis": sintesis,
        "secciones": secciones,
        "riesgos_criticos": criticos,
        "alertas": alertas_list,
        "limitaciones": limitaciones,
        "texto_plano": texto_plano,
    }


# -----------------------------------------------------------------------------
# API principal de análisis.
# -----------------------------------------------------------------------------

def analizar_empresa(datos_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Analiza una empresa y retorna un dict serializable en JSON."""
    if not isinstance(datos_dict, dict):
        raise TypeError("datos_dict debe ser un diccionario.")

    empresa = str(datos_dict.get("empresa", "Empresa sin nombre")).strip()
    cortes = datos_dict.get("cortes")

    if cortes is None:
        cortes = [{
            "fecha": datos_dict.get("fecha", None),
            "indicadores": datos_dict.get("indicadores", datos_dict.get("datos", {})),
        }]

    if not isinstance(cortes, list) or not cortes:
        raise ValueError("Debe suministrar un corte o una lista no vacía de cortes.")

    filas = []
    for corte in cortes:
        if not isinstance(corte, dict):
            raise TypeError("Cada corte debe ser un diccionario.")
        fecha = pd.to_datetime(corte.get("fecha"), errors="coerce")
        indicadores = corte.get("indicadores", corte.get("datos", {}))
        if not isinstance(indicadores, dict):
            raise TypeError("'indicadores' debe ser un diccionario {nombre: valor}.")
        for nombre, valor in indicadores.items():
            canonico = canonizar_indicador(nombre)
            if canonico is not None:
                filas.append({
                    "empresa": empresa,
                    "fecha": fecha,
                    "indicador": canonico,
                    "valor": parsear_numero(valor),
                    "unidad": INDICADORES[canonico]["unidad"],
                })

    if not filas:
        raise ValueError("No se encontraron indicadores soportados en datos_dict.")

    historial = pd.DataFrame(filas)
    return analizar_historial_empresa(historial, empresa=empresa)


def analizar_historial_empresa(historial: pd.DataFrame, empresa: Optional[str] = None) -> Dict[str, Any]:
    """Analiza el último corte disponible de una empresa y sus tendencias."""
    if historial.empty:
        raise ValueError("No hay datos para analizar.")

    historial = historial.copy()
    historial["fecha"] = pd.to_datetime(historial["fecha"], errors="coerce")
    if empresa is None:
        empresa = str(historial["empresa"].iloc[0])

    fechas_validas = historial["fecha"].dropna()
    fecha_analisis = fechas_validas.max() if not fechas_validas.empty else pd.NaT
    if pd.isna(fecha_analisis):
        ultimo = historial.copy()
    else:
        ultimo = historial[historial["fecha"] == fecha_analisis].copy()

    mapa_valores = ultimo.groupby("indicador")["valor"].last().to_dict()
    diagnosticos = []
    tendencias = {}
    for indicador in INDICADORES:
        valor = mapa_valores.get(indicador, np.nan)
        diagnosticos.append(diagnosticar_registro(indicador, valor, fecha_analisis))
        serie_ind = historial[historial["indicador"] == indicador]
        tendencias[indicador] = tendencia_indicador(serie_ind, indicador)

    df_diag = pd.DataFrame(diagnosticos)
    disponibles = df_diag[df_diag["valor"].notna()].copy()
    cobertura = len(disponibles) / len(INDICADORES)

    if disponibles.empty:
        score = np.nan
    else:
        score = float(np.average(disponibles["riesgo_individual"], weights=disponibles["peso"]))
    nivel, color = estado_score(score)

    riesgo_categoria = (
        disponibles.groupby("categoria")
        .apply(lambda x: np.average(x["riesgo_individual"], weights=x["peso"]), include_groups=False)
        .to_dict()
        if not disponibles.empty else {}
    )
    riesgo_categoria = {k: round(float(v), 2) for k, v in riesgo_categoria.items()}

    resumen = construir_resumen(empresa, fecha_analisis, df_diag, score, cobertura, tendencias)
    alertas = df_diag[df_diag["severidad"].isin(["critico", "alerta"])].sort_values(
        ["riesgo_individual", "indicador"], ascending=[False, True]
    )

    return {
        "empresa": empresa,
        "fecha_analisis": None if pd.isna(fecha_analisis) else fmt_fecha(fecha_analisis),
        "score_riesgo_financiero": None if pd.isna(score) else round(score, 2),
        "nivel_riesgo": nivel,
        "semaforo": color,
        "cobertura_datos_pct": round(cobertura * 100, 2),
        "indicadores_disponibles": int(len(disponibles)),
        "indicadores_esperados": int(len(INDICADORES)),
        "diagnosticos": df_diag.to_dict(orient="records"),
        "riesgo_por_categoria": riesgo_categoria,
        "tendencias": tendencias,
        "alertas_priorizadas": alertas[["indicador", "valor_formateado", "estado", "severidad", "riesgo_individual", "mensaje"]].to_dict(orient="records"),
        "resumen_ejecutivo": resumen,
        "recomendaciones": generar_recomendaciones(df_diag, score),
        "metadata": {
            "moneda_referencia": "COP",
            "metodologia": "Reglas heurísticas configurables con score ponderado por indicadores disponibles.",
            "limitacion": "Los valores suministrados son variaciones/ratios; no permiten calcular flujo de caja, cobertura de intereses, capital de trabajo ni modelos de insolvencia sin estados financieros absolutos."
        },
    }


# -----------------------------------------------------------------------------
# Visualización y reportes.
# -----------------------------------------------------------------------------

def color_severidad(severidad: str) -> str:
    return {
        "critico": "#dc2626", "alerta": "#f59e0b", "info": "#64748b", "ok": "#16a34a"
    }.get(severidad, "#64748b")


def generar_graficos(historial: pd.DataFrame, empresa: str, directorio_salida: str | Path) -> List[Path]:
    """Genera gráficos de tendencia por categorías con datos disponibles."""
    salida = Path(directorio_salida)
    salida.mkdir(parents=True, exist_ok=True)
    empresa_safe = re.sub(r"[^A-Za-z0-9_-]+", "_", empresa).strip("_") or "empresa"
    archivos = []

    datos = historial.copy()
    datos["fecha"] = pd.to_datetime(datos["fecha"], errors="coerce")
    datos = datos.dropna(subset=["fecha", "valor"])
    if datos.empty:
        return archivos

    for categoria in CATEGORIAS_ORDEN:
        indicadores_cat = [i for i, m in INDICADORES.items() if m["categoria"] == categoria]
        parte = datos[datos["indicador"].isin(indicadores_cat)].copy()
        if parte.empty:
            continue

        fig, ax = plt.subplots(figsize=(11, 5.5))
        for indicador, serie in parte.groupby("indicador"):
            unidad = INDICADORES[indicador]["unidad"]
            etiqueta = indicador + (" (x)" if unidad == "ratio" else " (%)")
            ax.plot(serie["fecha"], serie["valor"], marker="o", linewidth=2, label=etiqueta)

        ax.axhline(0, color="#94a3b8", linewidth=0.9)
        ax.set_title(f"{empresa} — Tendencia: {categoria}", loc="left", fontweight="bold")
        ax.set_xlabel("Fecha")
        ax.set_ylabel("Valor (% o x, según indicador)")
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best", fontsize=8)
        fig.autofmt_xdate()
        fig.tight_layout()

        ruta = salida / f"{empresa_safe}_tendencia_{normalizar_texto(categoria).replace(' ', '_')}.png"
        fig.savefig(ruta, dpi=160, bbox_inches="tight")
        plt.close(fig)
        archivos.append(ruta)

    return archivos


def resultados_a_dataframe(resultado: Dict[str, Any]) -> pd.DataFrame:
    columnas = [
        "indicador", "categoria", "valor_formateado", "estado", "severidad",
        "riesgo_individual", "peso", "mensaje"
    ]
    return pd.DataFrame(resultado["diagnosticos"])[columnas]


def construir_html_empresa(resultado: Dict[str, Any], rutas_graficos: List[Path]) -> str:
    """Crea HTML autónomo con semáforos, tablas, narrativa y gráficos."""
    diagnosticos = resultados_a_dataframe(resultado).copy()
    diagnosticos["semaforo"] = diagnosticos["severidad"].map(color_severidad)

    filas = []
    for _, r in diagnosticos.iterrows():
        filas.append(f"""
        <tr>
          <td>{r['indicador']}</td><td>{r['categoria']}</td><td>{r['valor_formateado']}</td>
          <td><span class='dot' style='background:{r['semaforo']}'></span>{r['estado']}</td>
          <td>{r['riesgo_individual']:.1f}</td><td>{r['mensaje']}</td>
        </tr>""")

    nivel = resultado["nivel_riesgo"]
    color_global = {
        "rojo": "#dc2626", "naranja": "#f97316", "amarillo": "#ca8a04", "verde": "#16a34a", "gris": "#64748b"
    }.get(resultado["semaforo"], "#64748b")

    resumen = resultado["resumen_ejecutivo"]
    secciones_html = "".join(
        f"<h3>{s['titulo']}</h3><p>{s['texto']}</p>" for s in resumen["secciones"]
    )
    limitaciones_html = "".join(f"<li>{x}</li>" for x in resumen["limitaciones"])
    recomendaciones_html = "".join(
        f"<li><strong>{r['prioridad']} · {r['frente']}:</strong> {r['accion']}</li>"
        for r in resultado["recomendaciones"]
    )
    graficos_html = "".join(
        f"<figure><img src='{ruta.name}' alt='Gráfico {ruta.stem}'><figcaption>{ruta.stem.replace('_', ' ')}</figcaption></figure>"
        for ruta in rutas_graficos
    ) or "<p>No se generaron gráficos: se requieren fecha y valores numéricos disponibles.</p>"

    score = resultado["score_riesgo_financiero"]
    score_txt = "N/D" if score is None else f"{score:.1f}/100"

    return f"""<!doctype html>
<html lang='es'>
<head>
<meta charset='utf-8'>
<title>Reporte financiero - {resultado['empresa']}</title>
<style>
@page {{ size: A4; margin: 1.3cm; }}
body {{ font-family: Arial, Helvetica, sans-serif; color:#172033; font-size: 11px; line-height:1.45; }}
h1 {{ margin-bottom:2px; font-size:24px; }} h2 {{ color:#0f3d63; margin-top:24px; border-bottom:1px solid #d9e2ec; padding-bottom:5px; }}
h3 {{ color:#164e63; margin-bottom:3px; }} p {{ margin-top:3px; }}
.meta {{ color:#475569; }}
.kpis {{ display:flex; gap:12px; margin:16px 0; }}
.kpi {{ border:1px solid #d9e2ec; border-radius:8px; padding:10px; min-width:145px; }}
.kpi .value {{ font-size:22px; font-weight:bold; color:{color_global}; }}
.badge {{ background:{color_global}; color:white; padding:4px 8px; border-radius:12px; font-weight:bold; }}
table {{ border-collapse:collapse; width:100%; margin-top:10px; font-size:9px; }}
th {{ background:#0f3d63; color:white; text-align:left; }} th, td {{ border:1px solid #d9e2ec; padding:6px; vertical-align:top; }}
tr:nth-child(even) {{ background:#f8fafc; }} .dot {{ height:9px; width:9px; display:inline-block; border-radius:50%; margin-right:5px; }}
figure {{ margin:14px 0; page-break-inside:avoid; }} img {{ max-width:100%; height:auto; border:1px solid #e2e8f0; }} figcaption {{ color:#64748b; font-size:9px; }}
.footer {{ margin-top:20px; color:#64748b; font-size:9px; }}
</style>
</head>
<body>
<h1>Reporte de diagnóstico financiero</h1>
<p class='meta'><strong>Empresa:</strong> {resultado['empresa']} &nbsp;|&nbsp; <strong>Fecha de análisis:</strong> {resultado['fecha_analisis'] or 'Sin fecha'} &nbsp;|&nbsp; <strong>Moneda de referencia:</strong> COP</p>
<div class='kpis'>
  <div class='kpi'><div>Score de riesgo</div><div class='value'>{score_txt}</div></div>
  <div class='kpi'><div>Nivel</div><div><span class='badge'>{nivel}</span></div></div>
  <div class='kpi'><div>Cobertura de datos</div><div class='value'>{resultado['cobertura_datos_pct']:.0f}%</div></div>
</div>
<h2>Resumen ejecutivo</h2>
<p><strong>{resumen['sintesis']}</strong></p>
{secciones_html}
<h3>Interpretación ejecutiva</h3>
<p>{resumen['texto_plano'].split('Interpretación ejecutiva: ')[-1].split('Limitaciones:')[0].strip()}</p>
<h2>Semáforo por indicador</h2>
<table><thead><tr><th>Indicador</th><th>Categoría</th><th>Valor</th><th>Estado</th><th>Riesgo</th><th>Interpretación</th></tr></thead>
<tbody>{''.join(filas)}</tbody></table>
<h2>Tendencias</h2>
{graficos_html}
<h2>Acciones priorizadas</h2>
<ul>{recomendaciones_html}</ul>
<h2>Limitaciones y calidad de datos</h2>
<ul>{limitaciones_html}</ul>
<p class='footer'>Reporte generado automáticamente. Los umbrales y el score son heurísticos configurables; valide cifras, notas contables, sector, deuda, covenants y flujo de caja antes de tomar decisiones.</p>
</body></html>"""


def guardar_reportes_empresa(
    resultado: Dict[str, Any],
    historial_empresa: pd.DataFrame,
    directorio_salida: str | Path,
    generar_pdf: bool = True,
) -> Dict[str, Any]:
    """Guarda JSON, CSV, HTML y, si es posible, PDF para una empresa."""
    salida = Path(directorio_salida)
    salida.mkdir(parents=True, exist_ok=True)
    nombre = re.sub(r"[^A-Za-z0-9_-]+", "_", resultado["empresa"]).strip("_") or "empresa"

    graficos = generar_graficos(historial_empresa, resultado["empresa"], salida)
    html = construir_html_empresa(resultado, graficos)

    ruta_html = salida / f"reporte_financiero_{nombre}.html"
    ruta_json = salida / f"analisis_financiero_{nombre}.json"
    ruta_csv = salida / f"diagnostico_financiero_{nombre}.csv"
    ruta_pdf = salida / f"reporte_financiero_{nombre}.pdf"

    ruta_html.write_text(html, encoding="utf-8")
    ruta_json.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    resultados_a_dataframe(resultado).to_csv(ruta_csv, index=False, encoding="utf-8-sig")

    archivos = {
        "html": str(ruta_html),
        "json": str(ruta_json),
        "csv": str(ruta_csv),
        "graficos": [str(p) for p in graficos],
    }
    if generar_pdf and WEASYPRINT_DISPONIBLE:
        HTML(filename=str(ruta_html), base_url=str(salida.resolve())).write_pdf(str(ruta_pdf))
        archivos["pdf"] = str(ruta_pdf)
    elif generar_pdf:
        archivos["pdf"] = "No generado: instale weasyprint (pip install weasyprint) y sus dependencias del sistema."
    return archivos


# -----------------------------------------------------------------------------
# Pipeline multiempresa.
# -----------------------------------------------------------------------------

def ejecutar_pipeline(
    ruta_entrada: str | Path,
    directorio_salida: str | Path = "output_financiero",
    hoja: int | str = 0,
    generar_pdf: bool = True,
) -> Dict[str, Any]:
    """Ejecuta el proceso completo: lectura, análisis multiempresa y reportes."""
    datos = leer_datos(ruta_entrada, hoja=hoja)
    salida = Path(directorio_salida)
    salida.mkdir(parents=True, exist_ok=True)

    resultados = []
    archivos_por_empresa = {}
    for empresa, historial in datos.groupby("empresa", sort=True):
        resultado = analizar_historial_empresa(historial, empresa=str(empresa))
        archivos = guardar_reportes_empresa(resultado, historial, salida, generar_pdf=generar_pdf)
        resultado["archivos"] = archivos
        resultados.append(resultado)
        archivos_por_empresa[str(empresa)] = archivos

    resumen_portafolio = pd.DataFrame([
        {
            "empresa": r["empresa"],
            "fecha_analisis": r["fecha_analisis"],
            "score_riesgo_financiero": r["score_riesgo_financiero"],
            "nivel_riesgo": r["nivel_riesgo"],
            "cobertura_datos_pct": r["cobertura_datos_pct"],
        }
        for r in resultados
    ]).sort_values("score_riesgo_financiero", ascending=False, na_position="last")

    ruta_portafolio = salida / "resumen_portafolio.csv"
    resumen_portafolio.to_csv(ruta_portafolio, index=False, encoding="utf-8-sig")

    payload = {
        "ejecucion_fecha": date.today().isoformat(),
        "moneda_referencia": "COP",
        "empresas_analizadas": len(resultados),
        "resultados": resultados,
        "resumen_portafolio_csv": str(ruta_portafolio),
    }
    (salida / "resultado_pipeline.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return payload
