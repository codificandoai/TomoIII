# MLOps: Circuito completo para desplegar el modelo "Predicción de retraso de vuelos"
## 1. Resumen del proyecto
**Nombre del repositorio:** `flight-delays`
**Objetivo:** Entrenar, empaquetar y exponer como API un modelo de machine learning que predice la probabilidad de que un vuelo que opera o aterriza en el aeropuerto de Santiago (SCL) tenga un retraso superior a 15 minutos.
**Flujo MLOps cubierto:**

```
Datos crudos → Ingeniería de features → Entrenamiento → Persistencia del modelo
→ Pruebas unitarias / integración / estrés → Contenerización → CI/CD
→ Despliegue en Render → API de predicción en producción
```

---

## 2. Estructura del repositorio

```
flight-delays/
├── .github/
│   └── workflows/
│       ├── ci.yml                # Pipeline de Integración Continua
│       └── cd.yml                # Pipeline de Entrega/Despliegue Continuo
├── challenge/                    # Paquete principal del modelo y API
│   ├── __init__.py               # Expone la app FastAPI
│   ├── api.py                    # Endpoints REST (health, predict)
│   ├── model.py                  # Lógica del modelo XGBoost + preprocesamiento
│   ├── model.pkl                 # Modelo entrenado serializado (joblib)
│   ├── exploration.ipynb         # Notebook del Data Scientist con EDA y pruebas
│   ├── flights_by_day_pro.png    # Visualizaciones generadas en el EDA
│   ├── flights_by_month.png
│   ├── top_airlines.png
│   └── feature/                  # Feature store con conocimiento de dominio
│       ├── aterrizaje.csv
│       ├── param-retraso-vuelos-bog.csv
│       ├── param-retraso-vuelos-scl.csv
│       └── razones-param.csv
├── data/
│   ├── data.csv                  # Dataset histórico (~68K vuelos SCL)
│   ├── post.json                 # Ejemplo mínimo de request a la API
│   ├── post-fligths.json         # Ejemplo batch de request/response
│   └── test-output.md            # Reporte histórico de cobertura
├── docs/
│   ├── challenge.md              # Documentación del challenge y decisiones de ML
│   ├── QA_model.png
│   ├── evidence/
│   ├── git/
│   └── library/
├── reports/
│   ├── coverage.xml              # Cobertura de pruebas (XML)
│   ├── junit.xml                 # Resultados de pruebas (JUnit)
│   └── stress-test.html          # Reporte de pruebas de estrés con Locust
├── tests/
│   ├── conftest.py               # Configuración de working dir para pytest
│   ├── api/
│   │   └── test_api.py           # Pruebas de integración de la API
│   ├── model/
│   │   └── test_model.py         # Pruebas unitarias del modelo
│   └── stress/
│       └── api_stress.py         # Escenarios de carga con Locust
├── Dockerfile                    # Imagen de producción
├── Makefile                      # Comandos de desarrollo, test y build
├── render.yaml                   # Configuración de despliegue en Render
├── requirements.txt              # Dependencias de producción/test
├── requirements-dev.txt          # Dependencias de desarrollo (visualización)
├── requirements-test.txt         # Dependencias de pruebas
├── .coveragerc                   # Configuración de cobertura
└── README.md                     # Descripción general del dataset
```

---

## 3. Análisis de archivos y propósito

### 3.1 `challenge/model.py` — Motor del modelo

`DelayModel` encapsula todo el ciclo de vida del modelo:

- **Features seleccionadas (Top 10):**

```python
TOP_10_FEATURES = [
    "OPERA_Latin American Wings", "MES_7", "MES_10",
    "OPERA_Grupo LATAM", "MES_12", "TIPOVUELO_I",
    "MES_4", "MES_11", "OPERA_Sky Airline", "OPERA_Copa Air",
]
```

- **Algoritmo:** `xgboost.XGBClassifier`.
- **Balanceo de clases:** calcula `scale_pos_weight = n_no_retrasos / n_retrasos` para compensar el desbalance entre vuelos puntuales y retrasados.
- **Hiperparámetros:**

| Parámetro | Valor |
|-----------|-------|
| `learning_rate` | 0.01 |
| `n_estimators` | 500 |
| `max_depth` | 3 |
| `subsample` | 0.8 |
| `colsample_bytree` | 0.8 |
| `eval_metric` | logloss |
| `random_state` | 1 |

**Métodos principales:**

- `preprocess(data, target_column=None)`: genera variables derivadas (`period_day`, `high_season`, `min_diff`), codifica con one-hot (`OPERA`, `TIPOVUELO`, `MES`) y alinea las columnas contra `TOP_10_FEATURES`.
- `preprocess_api(flights)`: adapta una lista de dicts (JSON de la API) al formato del modelo.
- `fit(features, target)`: entrena el XGBoost y persiste `model.pkl`.
- `predict(features)`: carga el modelo si es necesario y devuelve `[0, 1, ...]`.
- `train_from_csv(path)`: carga CSV, preprocesa, entrena y guarda.
- `_save()` / `_load()`: persistencia con `joblib`.

### 3.2 `challenge/api.py` — API REST con FastAPI

- **Objetivo:** exponer el modelo entrenado como servicio web.
- **Inicialización:** carga `model.pkl` si existe; si no, entrena automáticamente con `data/data.csv`.

**Endpoints:**

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Devuelve `{"status": "OK"}` |
| POST | `/predict` | Recibe `flights: [{OPERA, TIPOVUELO, MES}]` y devuelve `{"predict": [0|1]}` |

**Validaciones implementadas:**

- `MES` debe estar entre 1 y 12.
- `TIPOVUELO` debe ser `"I"` (internacional) o `"N"` (nacional).

Cualquier violación retorna HTTP 400.

### 3.3 `challenge/feature/` — Feature store de conocimiento de dominio

Archivos CSV con causas de retraso por aeropuerto y categoría. No son features directas del modelo, pero documentan el conocimiento que justifica la selección de variables:

- `aterrizaje.csv`: variables que afectan aterrizajes.
- `param-retraso-vuelos-bog.csv`: causas dominantes en Bogotá (altitud, pista única, tormentas).
- `param-retraso-vuelos-scl.csv`: causas dominantes en Santiago (capacidad de pista, clima, coordinación ATC).
- `razones-param.csv`: análisis estilo Ishikawa de causas raíz.

### 3.4 `data/data.csv` — Dataset histórico

Columnas originales del DS:

| Columna | Descripción |
|---------|-------------|
| `Fecha-I` | Fecha/hora programada |
| `Vlo-I` | Número de vuelo programado |
| `Ori-I` | Origen programado |
| `Des-I` | Destino programado |
| `Emp-I` | Aerolínea programada |
| `Fecha-O` | Fecha/hora real de operación |
| `Vlo-O` | Número de vuelo operado |
| `Ori-O` | Origen operado |
| `Des-O` | Destino operado |
| `Emp-O` | Aerolínea operada |
| `DIA`, `MES`, `AÑO` | Componentes de fecha |
| `DIANOM` | Día de la semana |
| `TIPOVUELO` | I = Internacional, N = Nacional |
| `OPERA` | Nombre de aerolínea operadora |
| `SIGLAORI` | Nombre ciudad origen |
| `SIGLADES` | Nombre ciudad destino |

Variables derivadas en el preprocesamiento:

- `high_season`: 1 si la fecha cae en temporada alta.
- `min_diff`: diferencia en minutos entre `Fecha-O` y `Fecha-I`.
- `period_day`: mañana, tarde o noche según `Fecha-I`.
- `delay`: target binario, 1 si `min_diff > 15` minutos.

### 3.5 `tests/`

- `tests/model/test_model.py`: 18+ casos de prueba del preprocesamiento, entrenamiento, predicción, persistencia y compatibilidad.
- `tests/api/test_api.py`: 4 casos de integración de `/predict` con `TestClient` de FastAPI.
- `tests/stress/api_stress.py`: escenarios de carga con Locust (100 usuarios, 60 s).
- `tests/conftest.py`: cambia el directorio de trabajo para que las rutas relativas a `data/data.csv` funcionen.

### 3.6 `Makefile`

| Target | Acción |
|--------|--------|
| `make venv` | Crea entorno virtual |
| `make install` | Instala todas las dependencias |
| `make model-test` | Ejecuta pruebas del modelo con cobertura |
| `make api-test` | Ejecuta pruebas de API con cobertura |
| `make stress-test` | Lanza Locust contra `https://flight-delays-v10p.onrender.com` |
| `make build` | Genera artefacto Python wheel |

### 3.7 `Dockerfile`

- Base: `python:3.11-slim`.
- Expone el puerto 8080.
- Comando final: `uvicorn challenge.api:app --host 0.0.0.0 --port 8080`.

### 3.8 `render.yaml`

Configuración de despliegue nativa en Render:

```yaml
services:
  - type: web
    name: flight-api
    env: python
    buildCommand: "pip install --upgrade pip setuptools wheel && pip install -r requirements.txt"
    startCommand: "uvicorn challenge.api:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.9
```

---

## 4. Machine Learning: cómo predice el modelo

### 4.1 Definición del problema

- **Tipo:** clasificación binaria.
- **Target:** `delay` = 1 si el retraso real supera 15 minutos; 0 en caso contrario.
- **Input de producción:** únicamente `OPERA`, `TIPOVUELO` y `MES`.

### 4.2 Pipeline de predicción

```
JSON de entrada
    │
    ▼
┌─────────────────┐
│  Validación     │  MES ∈ [1,12], TIPOVUELO ∈ {I,N}
│     API           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  One-hot encode │  OPERA_* + TIPOVUELO_* + MES_*
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Alineación a    │  Reindexar contra TOP_10_FEATURES
│ Top 10 features │  Valores faltantes = 0
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ XGBoost Classifier│  Predice 0 (puntual) o 1 (retrasado)
└─────────────────┘
```

### 4.3 Por qué estas 10 features

El Data Scientist evaluó 6 combinaciones de modelo/features/balanceo. El ganador fue **XGBoost + Top 10 + balanceo**.

| Modelo | Features | Balance | Recall retrasos | F1 retrasos |
|--------|----------|---------|-----------------|-------------|
| XGBoost | Top 10 | Sí | > 0.60 | > 0.30 |
| XGBoost | Todas | No | ~ 0.00 | ~ 0.00 |
| LogReg | Top 10 | Sí | ~ 0.60 | ~ 0.36 |

Las 10 features seleccionadas representan:

- **Aerolíneas con retrasos sistémicos:** `Latin American Wings`, `Grupo LATAM`, `Sky Airline`, `Copa Air`.
- **Meses con picos climáticos/congestión:** abril, julio, octubre, noviembre, diciembre.
- **Tipo de vuelo internacional:** mayor complejidad operativa.

### 4.4 Manejo del desbalance

Los vuelos puntuales son la mayoría. Sin balanceo el modelo predice siempre la clase mayoritaria. `scale_pos_weight` ajusta el peso de los errores en la clase minoritaria (retraso), permitiendo detectar ~69% de los retrasos reales.

---

## 5. GitHub Actions: CI/CD

### 5.1 `ci.yml` — Integración Continua

```yaml
name: CI Pipeline
on: [push, pull_request]
```

**Jobs:**

1. Checkout del repositorio.
2. Setup Python 3.9.
3. Instalación de dependencias desde `requirements.txt` + `pytest pytest-cov`.
4. Ejecuta `make model-test`.
5. Ejecuta `make api-test`.

### 5.2 `cd.yml` — Entrega/Despliegue Continuo

```yaml
name: CD Pipeline
on:
  push:
    branches: [main]
```

**Jobs:**

1. Instala Python 3.9 y dependencias.
2. Ejecuta `make model-test`.
3. Ejecuta `make api-test`.
4. Ejecuta `make stress-test` contra la API desplegada en Render.
5. Despliega automáticamente en Render usando `johnbeynon/render-deploy-action@v0.0.8`.

**Secretos requeridos en GitHub:**

- `RENDER_SERVICE_ID`
- `RENDER_API_KEY`

### 5.3 Flujo de CI/CD

```
Developer hace push
        │
        ▼
┌───────────────┐
│   CI Pipeline  │  push / pull_request
│  · model-test  │
│  · api-test    │
└───────┬───────┘
        │ OK
        ▼
┌───────────────┐
│ Merge a main   │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│   CD Pipeline  │
│  · model-test  │
│  · api-test    │
│  · stress-test │
└───────┬───────┘
        │ OK
        ▼
┌───────────────┐
│ Deploy Render  │
└───────────────┘
```

---

## 6. Circuito completo MLOps: desarrollo → producción

### 6.1 Fase 1: Exploración y entrenamiento

- El Data Scientist trabaja en `challenge/exploration.ipynb`.
- Selecciona XGBoost + Top 10 features + balanceo.
- Genera visualizaciones en `challenge/*.png`.

### 6.2 Fase 2: Producción del código

- Se implementa `DelayModel` en `challenge/model.py`.
- Se encapsula la API en `challenge/api.py`.
- Se serializa el modelo en `challenge/model.pkl`.

### 6.3 Fase 3: Pruebas automatizadas

- `make model-test`: valida preprocesamiento, entrenamiento y predicción.
- `make api-test`: valida contrato y validaciones de la API.
- Cobertura exportada a `reports/coverage.xml` y `reports/junit.xml`.

### 6.4 Fase 4: Contenerización

```bash
docker build -t flight-delay-api .
docker run -p 8080:8080 flight-delay-api
```

### 6.5 Fase 5: CI/CD con GitHub Actions

- Cada push/PR ejecuta pruebas.
- Cada merge a `main` ejecuta pruebas + estrés + despliegue automático en Render.

### 6.6 Fase 6: Producción

- Render ejecuta `uvicorn challenge.api:app` en el puerto dinámico `$PORT`.
- La API carga `model.pkl` o reentrena con `data.csv` si no existe.
- Clientes consumen `/health` y `/predict`.

---

## 7. API: contrato y ejemplos

### 7.1 Health check

```bash
curl https://flight-delays-v10p.onrender.com/health
```

**Respuesta:**

```json
{"status": "OK"}
```

### 7.2 Predicción

**Request:**

```bash
curl -X POST https://flight-delays-v10p.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{
    "flights": [
      {"OPERA": "Grupo LATAM", "TIPOVUELO": "I", "MES": 12}
    ]
  }'
```

**Respuesta exitosa (200):**

```json
{"predict": [1]}
```

**Error de validación (400):**

```json
{"detail": "Invalid MES value"}
```

---

## 8. Dependencias principales

| Paquete | Versión | Uso |
|---------|---------|-----|
| fastapi | 0.104.1 | Framework web/API |
| uvicorn | 0.24.0 | Servidor ASGI |
| xgboost | 1.7.6 | Modelo de clasificación |
| scikit-learn | 1.3.2 | Métricas y splits |
| pandas | 2.1.4 | Manipulación de datos |
| numpy | 1.24.3 | Operaciones numéricas |
| joblib | 1.3.2 | Serialización del modelo |
| pydantic | 2.5.0 | Validación de esquemas |
| pytest | 7.4.3 | Framework de pruebas |
| pytest-cov | 4.1.0 | Cobertura de pruebas |
| locust | ~1.6 | Pruebas de carga |
| httpx | 0.27.0 | Cliente HTTP para tests |

---

## 9. Métricas esperadas

Según `docs/challenge.md` y las pruebas:

| Clase | Métrica | Umbral |
|-------|---------|--------|
| Retraso (1) | Recall | > 0.60 |
| Retraso (1) | F1-score | > 0.30 |
| Puntual (0) | Recall | < 0.60 |
| Puntual (0) | F1-score | < 0.70 |

---

## 10. Observaciones y notas de implementación

- El archivo `model.pkl` ya está versionado, por lo que el despliegue puede iniciar inmediatamente sin necesidad de reentrenar.
- Si `model.pkl` no existe, `api.py` entrena automáticamente con `data/data.csv` al arrancar el contenedor.
- `preprocess` es dual: devuelve `(features, target)` si se pasa `target_column`; de lo contrario solo devuelve `features`.
- La API solo requiere 3 campos de entrada (`OPERA`, `TIPOVUELO`, `MES`), aunque el dataset histórico tenga muchas columnas.
- La prueba de estrés apunta a la URL pública en Render; antes de ejecutar CD local es necesario configurar los secretos `RENDER_SERVICE_ID` y `RENDER_API_KEY`.

---

## 11. Comandos de uso rápido

```bash
# Crear entorno e instalar
make venv
source .venv/bin/activate
make install

# Entrenar y probar localmente
python -c "from challenge.model import DelayModel; DelayModel().train_from_csv('data/data.csv')"

# Ejecutar tests
make model-test
make api-test

# Ejecutar API local
uvicorn challenge.api:app --host 0.0.0.0 --port 8080

# Docker
docker build -t flight-delay-api .
docker run -p 8080:8080 flight-delay-api

# Pruebas de estrés contra producción
make stress-test
```

---

## 12. Conclusión

El proyecto `flight-delays` implementa un pipeline MLOps completo y operativo:

- **Desarrollo:** notebook de exploración, feature store de dominio y código modular.
- **Entrenamiento:** XGBoost con balanceo de clases y selección de Top 10 features.
- **Pruebas:** unitarias, de integración, cobertura y estrés.
- **Empaquetado:** Dockerfile con Python 3.11.
- **CI/CD:** GitHub Actions con validación automática y despliegue a Render.
- **Producción:** API REST FastAPI accesible públicamente con health check y predicción batch.

Este circuito permite pasar de un experimento en Jupyter a un modelo desplegado y consumible mediante HTTP, con garantías de calidad a través de tests automatizados y despliegue continuo.

---

# 13. Análisis técnico línea por línea

A continuación se documenta cada archivo relevante del proyecto, explicando línea a línea su función dentro del circuito MLOps.

---

## 13.1 `challenge/model.py`

```python
import pandas as pd
```
- **Línea 1:** Importa pandas para manipulación de DataFrames.

```python
import numpy as np
```
- **Línea 2:** Importa NumPy para operaciones numéricas y generación del target binario.

```python
import os
```
- **Línea 3:** Importa `os` para construir rutas absolutas del modelo serializado.

```python
import joblib
```
- **Línea 4:** Importa joblib para guardar/cargar el modelo entrenado en disco.

```python
import xgboost as xgb
```
- **Línea 5:** Importa XGBoost, la librería del clasificador usado.

```python
from datetime import datetime
```
- **Línea 7:** Importa `datetime` para parsear fechas y calcular diferencias de tiempo.

```python
from typing import Tuple, Union, List
```
- **Línea 8:** Importa tipos genéricos para anotaciones de tipo.

```python
class DelayModel:
```
- **Línea 11:** Define la clase principal que encapsula todo el modelo.

```python
    TOP_10_FEATURES = [...]
```
- **Líneas 13-24:** Lista las 10 variables seleccionadas. Son las columnas finales que espera el modelo.

```python
    THRESHOLD_IN_MINUTES = 15
```
- **Línea 26:** Umbral que define si un vuelo se considera retrasado (> 15 minutos).

```python
    _MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.pkl")
```
- **Líneas 28-30:** Construye la ruta absoluta al archivo `model.pkl` al lado de `model.py`.

```python
    def __init__(self):
        self._model = None
        self._feature_columns = None
```
- **Líneas 32-36:** Constructor. Inicializa el modelo como `None` hasta que se entrena o carga.

```python
    @property
    def feature_columns(self) -> List[str]:
```
- **Líneas 38-43:** Propiedad que retorna las columnas guardadas tras entrenar, o las `TOP_10_FEATURES` por defecto.

```python
    def train_from_csv(self, csv_path: str) -> None:
```
- **Líneas 45-49:** Lee un CSV, preprocesa con target `delay` y ejecuta `fit`. Es el punto de entrada para entrenar automáticamente.

```python
    def preprocess_api(self, flights: List[dict]) -> pd.DataFrame:
```
- **Líneas 51-54:** Convierte una lista de dicts (JSON de la API) en DataFrame y llama a `preprocess`.

```python
    def preprocess(self, data: pd.DataFrame, target_column: str = None) -> Union[Tuple[pd.DataFrame, pd.DataFrame], pd.DataFrame]:
```
- **Líneas 56-60:** Firma del método de preprocesamiento. Puede devolver features solas o features + target.

```python
        data = data.copy()
```
- **Línea 73:** Copia el DataFrame de entrada para no mutar los datos originales.

```python
        if "Fecha-I" in data.columns:
            data["period_day"] = data["Fecha-I"].apply(self._get_period_day)
            data["high_season"] = data["Fecha-I"].apply(self._is_high_season)
```
- **Líneas 76-78:** Si el dataset histórico tiene `Fecha-I`, genera variables derivadas: franja del día y temporada alta.

```python
        if "Fecha-O" in data.columns and "Fecha-I" in data.columns:
            data["min_diff"] = data.apply(self._get_min_diff, axis=1)
```
- **Líneas 80-81:** Si existen fecha programada y real, calcula la diferencia en minutos.

```python
        dummies_list = [
            pd.get_dummies(data["OPERA"], prefix="OPERA"),
            pd.get_dummies(data["TIPOVUELO"], prefix="TIPOVUELO"),
            pd.get_dummies(data["MES"], prefix="MES"),
        ]
```
- **Líneas 84-88:** Codifica one-hot las variables categóricas principales: aerolínea, tipo de vuelo y mes.

```python
        if "period_day" in data.columns:
            dummies_list.append(pd.get_dummies(data["period_day"], prefix="period_day"))
        if "high_season" in data.columns:
            dummies_list.append(data[["high_season"]])
```
- **Líneas 89-92:** Añade dummies de `period_day` y la columna numérica `high_season` si están disponibles.

```python
        features = pd.concat(dummies_list, axis=1)
        features = features.reindex(columns=self.feature_columns, fill_value=0)
```
- **Líneas 94-95:** Concatena todas las variables y reindexa al orden esperado, rellenando con 0 las columnas ausentes.

```python
        if target_column:
            if "min_diff" not in data.columns:
                data["min_diff"] = data.apply(self._get_min_diff, axis=1)
            data[target_column] = np.where(data["min_diff"] > self.THRESHOLD_IN_MINUTES, 1, 0)
            target = data[[target_column]]
            return features, target
        return features
```
- **Líneas 97-104:** Si se solicita target, genera la columna binaria `delay` usando `min_diff > 15`. Devuelve features y target; si no, solo features.

```python
    def fit(self, features: pd.DataFrame, target: pd.DataFrame) -> None:
```
- **Líneas 106-110:** Método de entrenamiento del XGBoost.

```python
        self._feature_columns = features.columns.tolist()
```
- **Línea 118:** Guarda el orden real de columnas usado durante el entrenamiento.

```python
        target_values = target.iloc[:, 0]
        n_y0 = int((target_values == 0).sum())
        n_y1 = int((target_values == 1).sum())
        scale = n_y0 / n_y1
```
- **Líneas 120-123:** Calcula el peso de balanceo como cociente entre clase mayoritaria y minoritaria.

```python
        self._model = xgb.XGBClassifier(
            random_state=1,
            learning_rate=0.01,
            scale_pos_weight=scale,
            n_estimators=500,
            max_depth=3,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
        )
        self._model.fit(features, target_values)
        self._save()
```
- **Líneas 125-137:** Crea el clasificador XGBoost con los hiperparámetros elegidos, entrena con los datos y guarda el modelo.

```python
    def predict(self, features: pd.DataFrame) -> List[int]:
```
- **Líneas 139-156:** Si el modelo no está cargado, lo carga desde disco; luego predice y devuelve lista de enteros.

```python
    def _save(self) -> None:
        joblib.dump({"model": self._model, "feature_columns": self._feature_columns}, self._MODEL_PATH)
```
- **Líneas 158-163:** Persiste el modelo y el orden de columnas en `model.pkl`.

```python
    def _load(self) -> None:
        saved = joblib.load(self._MODEL_PATH)
        if isinstance(saved, dict):
            self._model = saved["model"]
            self._feature_columns = saved.get("feature_columns")
        else:
            self._model = saved
```
- **Líneas 165-172:** Carga el artefacto. Soporta el formato actual (diccionario) y el formato antiguo (modelo crudo).

```python
    @staticmethod
    def _get_min_diff(row: pd.Series) -> float:
        fecha_o = datetime.strptime(row["Fecha-O"], "%Y-%m-%d %H:%M:%S")
        fecha_i = datetime.strptime(row["Fecha-I"], "%Y-%m-%d %H:%M:%S")
        return ((fecha_o - fecha_i).total_seconds()) / 60
```
- **Líneas 174-179:** Calcula la diferencia en minutos entre fecha real y fecha programada.

```python
    @staticmethod
    def _get_period_day(date_str: str) -> str:
```
- **Líneas 181-200:** Clasifica la hora en mañana, tarde o noche según `Fecha-I`.

```python
    @staticmethod
    def _is_high_season(date_str: str) -> int:
```
- **Líneas 202-216:** Determina si la fecha cae en temporada alta (15 dic - 3 mar, 15-31 jul, 11-30 sep).

---

## 13.2 `challenge/api.py`

```python
import os
```
- **Línea 1:** Necesario para verificar la existencia del modelo serializado y del CSV.

```python
import fastapi
from fastapi import HTTPException
from pydantic import BaseModel
from typing import List
```
- **Líneas 3-6:** Importa FastAPI, excepciones HTTP, modelos Pydantic y tipo lista.

```python
from challenge.model import DelayModel
```
- **Línea 8:** Importa la clase del modelo.

```python
app = fastapi.FastAPI()
model = DelayModel()
```
- **Líneas 10-11:** Crea la aplicación FastAPI y una instancia del modelo.

```python
if os.path.exists(DelayModel._MODEL_PATH):
    model._load()
else:
    _data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "data.csv")
    if os.path.exists(_data_path):
        model.train_from_csv(_data_path)
```
- **Líneas 13-21:** Al iniciar la aplicación, carga el modelo si existe; si no, lo entrena automáticamente con `data.csv`.

```python
class FlightInput(BaseModel):
    OPERA: str
    TIPOVUELO: str
    MES: int
```
- **Líneas 24-27:** Esquema Pydantic para un vuelo individual.

```python
class PredictInput(BaseModel):
    flights: List[FlightInput]
```
- **Líneas 30-31:** Esquema Pydantic para la lista de vuelos en el request.

```python
@app.get("/health", status_code=200)
async def get_health() -> dict:
    return {"status": "OK"}
```
- **Líneas 34-38:** Endpoint de salud. Útil para health checks y monitoreo.

```python
@app.post("/predict", status_code=200)
async def post_predict(data: PredictInput) -> dict:
    for flight in data.flights:
        if flight.MES < 1 or flight.MES > 12:
            raise HTTPException(status_code=400, detail="Invalid MES value")
        if flight.TIPOVUELO not in ("I", "N"):
            raise HTTPException(status_code=400, detail="Invalid TIPOVUELO value")
```
- **Líneas 41-47:** Valida que `MES` esté entre 1 y 12 y que `TIPOVUELO` sea `I` o `N`; de lo contrario lanza 400.

```python
    flights_list = [f.dict() for f in data.flights]
    features = model.preprocess_api(flights_list)
    predictions = model.predict(features)
    return {"predict": predictions}
```
- **Líneas 49-52:** Convierte los vuelos a dicts, genera las features y devuelve las predicciones.

---

## 13.3 `challenge/__init__.py`

```python
from challenge.api import app

application = app
```
- **Línea 1:** Importa la instancia FastAPI desde `api.py`.
- **Línea 3:** Expone `application` como alias, útil para servidores WSGI/ASGI que esperen esa variable.

---

## 13.4 `.github/workflows/ci.yml`

```yaml
name: CI Pipeline
```
- **Línea 1:** Nombre del workflow.

```yaml
on: [push, pull_request]
```
- **Línea 2:** Se ejecuta en cada push y en cada pull request.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
```
- **Líneas 4-6:** Define un job llamado `test` que corre en Ubuntu.

```yaml
      - uses: actions/checkout@v4
```
- **Línea 8:** Descarga el repositorio.

```yaml
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.9'
```
- **Líneas 10-13:** Instala Python 3.9.

```yaml
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov
```
- **Líneas 15-20:** Actualiza pip, instala dependencias de producción y pytest con cobertura.

```yaml
      - name: Run model tests
        run: make model-test
```
- **Líneas 22-23:** Ejecuta las pruebas del modelo.

```yaml
      - name: Run API tests
        run: make api-test
```
- **Líneas 25-26:** Ejecuta las pruebas de la API.

---

## 13.5 `.github/workflows/cd.yml`

```yaml
name: CD Pipeline
on:
  push:
    branches: [main]
```
- **Líneas 1-4:** Se ejecuta solo cuando hay push a `main`.

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
```
- **Líneas 6-8:** Job de despliegue en Ubuntu.

```yaml
      - uses: actions/checkout@v4
```
- **Línea 10:** Descarga el código.

```yaml
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.9'
```
- **Líneas 13-16:** Configura Python 3.9.

```yaml
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov
```
- **Líneas 18-22:** Instala dependencias.

```yaml
      - name: Run all tests
        run: |
          make model-test
          make api-test
          make stress-test
```
- **Líneas 25-29:** Ejecuta tests del modelo, API y prueba de estrés contra la API en Render.

```yaml
      - name: Deploy to Render
        uses: johnbeynon/render-deploy-action@v0.0.8
        with:
          service-id: ${{ secrets.RENDER_SERVICE_ID }}
          api-key: ${{ secrets.RENDER_API_KEY }}
```
- **Líneas 32-36:** Despliega automáticamente en Render usando secretos configurados en GitHub.

---

## 13.6 `Dockerfile`

```dockerfile
FROM python:3.11-slim
```
- **Línea 1:** Imagen base ligera de Python 3.11.

```dockerfile
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*
```
- **Línea 4:** Instala compiladores necesarios para dependencias nativas de XGBoost y scikit-learn.

```dockerfile
WORKDIR /app
```
- **Línea 6:** Establece el directorio de trabajo.

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt
```
- **Líneas 7-9:** Copia e instala dependencias aprovechando caché de capas.

```dockerfile
COPY . .
```
- **Línea 11:** Copia el resto del proyecto al contenedor.

```dockerfile
EXPOSE 8080
CMD ["uvicorn", "challenge.api:app", "--host", "0.0.0.0", "--port", "8080"]
```
- **Líneas 12-13:** Expone el puerto 8080 y define el comando de arranque del servidor.

---

## 13.7 `Makefile`

```makefile
.ONESHELL:
```
- **Línea 1:** Ejecuta cada receta en una sola shell.

```makefile
ENV_PREFIX=$(shell python -c "if __import__('pathlib').Path('.venv/bin/pip').exists(): print('.venv/bin/')")
```
- **Línea 2:** Detecta si existe un entorno virtual para prefijar comandos (aunque no se usa directamente en los targets).

```makefile
.PHONY: help
help:
	@echo "Usage: make <target>"
```
- **Líneas 4-9:** Muestra ayuda listando los targets comentados.

```makefile
.PHONY: venv
venv:
	@echo "Creating virtualenv ..."
	@rm -rf .venv
	@python3 -m venv .venv
	@./.venv/bin/pip install -U pip
```
- **Líneas 11-18:** Crea un entorno virtual limpio.

```makefile
.PHONY: install
install:
	pip install -r requirements-dev.txt
	pip install -r requirements-test.txt
	pip install -r requirements.txt
```
- **Líneas 20-24:** Instala las tres listas de dependencias.

```makefile
STRESS_URL = https://flight-delays-v10p.onrender.com
.PHONY: stress-test
stress-test:
	mkdir reports || true
	locust -f tests/stress/api_stress.py --print-stats --html reports/stress-test.html --run-time 60s --headless --users 100 --spawn-rate 1 -H $(STRESS_URL)
```
- **Líneas 26-31:** Define la URL de estrés y lanza Locust con 100 usuarios durante 60 segundos.

```makefile
.PHONY: model-test
model-test:
	mkdir reports || true
	pytest --cov-config=.coveragerc --cov-report term --cov-report html:reports/html --cov-report xml:reports/coverage.xml --junitxml=reports/junit.xml --cov=challenge tests/model
```
- **Líneas 33-36:** Ejecuta tests del modelo con cobertura en múltiples formatos.

```makefile
.PHONY: api-test
api-test:
	mkdir reports || true
	pytest --cov-config=.coveragerc --cov-report term --cov-report html:reports/html --cov-report xml:reports/coverage.xml --junitxml=reports/junit.xml --cov=challenge tests/api
```
- **Líneas 38-41:** Ejecuta tests de API con cobertura.

```makefile
.PHONY: build
build:
	python setup.py bdist_wheel
```
- **Líneas 43-45:** Target para generar un wheel local. Nota: actualmente no existe `setup.py`.

---

## 13.8 `render.yaml`

```yaml
services:
  - type: web
    name: flight-api
    env: python
```
- **Líneas 1-4:** Declara un servicio web de tipo Python en Render.

```yaml
    buildCommand: "pip install --upgrade pip setuptools wheel && pip install -r requirements.txt"
```
- **Línea 5:** Comando de build: instala dependencias.

```yaml
    startCommand: "uvicorn challenge.api:app --host 0.0.0.0 --port $PORT"
```
- **Línea 6:** Comando de inicio usando el puerto dinámico que asigna Render.

```yaml
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.9
```
- **Líneas 7-9:** Fija la versión de Python a 3.11.9.

---

## 13.9 `requirements.txt`

```text
# FIXED para Render 2026
setuptools==69.0.0
wheel==0.44.0
pip==24.0
```
- **Líneas 1-4:** Fija herramientas de empaquetado para evitar incompatibilidades en Render.

```text
fastapi==0.104.1
uvicorn[standard]==0.24.0
```
- **Líneas 6-7:** Framework web y servidor ASGI.

```text
xgboost==1.7.6
joblib==1.3.2
pandas==2.1.4
numpy==1.24.3
scikit-learn==1.3.2
pydantic==2.5.0
```
- **Líneas 8-13:** Librerías de ML, datos y validación.

```text
pytest==7.4.3
pytest-cov==4.1.0
httpx==0.27.0  # Para api-test
```
- **Líneas 14-16:** Testing, cobertura y cliente HTTP para tests de FastAPI.

---

## 13.10 `requirements-dev.txt`

```text
matplotlib~=3.7.2
seaborn~=0.12.2
```
- Librerías de visualización usadas en el notebook de exploración.

---

## 13.11 `requirements-test.txt`

```text
locust~=1.6
coverage~=5.5
pytest~=6.2.5
pytest-cov~=2.12.1
mockito~=1.2.2
```
- Dependencias de pruebas: Locust para estrés, coverage, pytest, pytest-cov y mockito.

---

## 13.12 `tests/api/test_api.py`

```python
import unittest
from fastapi.testclient import TestClient
from challenge import app
```
- **Líneas 1-4:** Importa unittest, cliente de test de FastAPI y la app.

```python
class TestBatchPipeline(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
```
- **Líneas 7-9:** Clase de pruebas. `setUp` crea un cliente de test para cada caso.

```python
    def test_should_get_predict(self):
        data = {"flights": [{"OPERA": "Aerolineas Argentinas", "TIPOVUELO": "N", "MES": 3}]}
        response = self.client.post("/predict", json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"predict": [0]})
```
- **Líneas 11-24:** Prueba un vuelo válido y verifica respuesta 200 con predicción `[0]`.

```python
    def test_should_failed_unkown_column_1(self):
        data = {"flights": [{"OPERA": "Aerolineas Argentinas", "TIPOVUELO": "N", "MES": 13}]}
        response = self.client.post("/predict", json=data)
        self.assertEqual(response.status_code, 400)
```
- **Líneas 27-39:** Prueba error 400 cuando `MES` es 13 (fuera de rango).

```python
    def test_should_failed_unkown_column_2(self):
        data = {"flights": [{"OPERA": "Aerolineas Argentinas", "TIPOVUELO": "O", "MES": 13}]}
        response = self.client.post("/predict", json=data)
        self.assertEqual(response.status_code, 400)
```
- **Líneas 41-53:** Prueba error 400 cuando `TIPOVUELO` no es `I` o `N`.

```python
    def test_should_failed_unkown_column_3(self):
        data = {"flights": [{"OPERA": "Argentinas", "TIPOVUELO": "O", "MES": 13}]}
        response = self.client.post("/predict", json=data)
        self.assertEqual(response.status_code, 400)
```
- **Líneas 55-67:** Caso adicional con múltiples valores inválidos.

---

## 13.13 `tests/model/test_model.py`

```python
import unittest, os, pandas as pd, numpy as np, joblib
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from challenge.model import DelayModel
```
- **Líneas 1-9:** Importa librerías de test, sklearn y el modelo.

```python
class TestModel(unittest.TestCase):
    FEATURES_COLS = [...]
    TARGET_COL = ["delay"]
```
- **Líneas 11-28:** Define constantes con las features y el target esperados.

```python
    def setUp(self) -> None:
        super().setUp()
        self.model = DelayModel()
        self.data = pd.read_csv(filepath_or_buffer="../data/data.csv")
```
- **Líneas 31-34:** Crea una instancia del modelo y carga los datos históricos antes de cada test.

```python
    def test_model_preprocess_for_training(self):
        features, target = self.model.preprocess(data=self.data, target_column="delay")
        assert isinstance(features, pd.DataFrame)
        assert features.shape[1] == len(self.FEATURES_COLS)
        assert set(features.columns) == set(self.FEATURES_COLS)
        assert isinstance(target, pd.DataFrame)
        assert target.shape[1] == len(self.TARGET_COL)
```
- **Líneas 37-51:** Verifica que `preprocess` con target devuelva features y target con las dimensiones correctas.

```python
    def test_model_preprocess_for_serving(self):
        features = self.model.preprocess(data=self.data)
        assert isinstance(features, pd.DataFrame)
        assert features.shape[1] == len(self.FEATURES_COLS)
```
- **Líneas 54-63:** Verifica el modo de serving sin target.

```python
    def test_model_fit(self):
        features, target = self.model.preprocess(data=self.data, target_column="delay")
        _, features_validation, _, target_validation = train_test_split(features, target, test_size=0.33, random_state=42)
        self.model.fit(features=features, target=target)
        predicted_target = self.model._model.predict(features_validation)
        report = classification_report(target_validation, predicted_target, output_dict=True)
        assert report["0"]["recall"] < 0.60
        assert report["0"]["f1-score"] < 0.70
        assert report["1"]["recall"] > 0.60
        assert report["1"]["f1-score"] > 0.30
```
- **Líneas 66-90:** Entrena, predice en validación y comprueba los umbrales de recall/f1.

```python
    def test_model_predict(self):
        features = self.model.preprocess(data=self.data)
        predicted_targets = self.model.predict(features=features)
        assert isinstance(predicted_targets, list)
        assert len(predicted_targets) == features.shape[0]
        assert all(isinstance(predicted_target, int) for predicted_target in predicted_targets)
```
- **Líneas 93-106:** Verifica que `predict` devuelva una lista de enteros de longitud correcta.

```python
    def test_preprocess_api_input(self):
        flights = [
            {"OPERA": "Grupo LATAM", "TIPOVUELO": "I", "MES": 12},
            {"OPERA": "Latin American Wings", "TIPOVUELO": "N", "MES": 7},
            {"OPERA": "Sky Airline", "TIPOVUELO": "I", "MES": 4},
        ]
        features = self.model.preprocess_api(flights)
        assert features.shape == (3, len(self.FEATURES_COLS))
```
- **Líneas 108-118:** Prueba `preprocess_api` con entrada de API.

```python
    def test_feature_alignment(self):
        api_data = pd.DataFrame([{"OPERA": "Unknown Airline", "TIPOVUELO": "N", "MES": 2}])
        features = self.model.preprocess(api_data)
        assert features.shape == (1, len(self.FEATURES_COLS))
        assert (features.iloc[0] == 0).all()
```
- **Líneas 120-127:** Verifica que valores desconocidos generen una fila de ceros alineada.

```python
    def test_predict_single_flight(self):
        api_data = pd.DataFrame([{"OPERA": "Grupo LATAM", "TIPOVUELO": "N", "MES": 3}])
        features = self.model.preprocess(api_data)
        predictions = self.model.predict(features)
        assert isinstance(predictions, list)
        assert len(predictions) == 1
        assert predictions[0] in (0, 1)
```
- **Líneas 129-138:** Prueba predicción de un único vuelo.

```python
    def test_predict_output_values_are_binary(self):
        features = self.model.preprocess(self.data)
        predictions = self.model.predict(features)
        assert all(p in (0, 1) for p in predictions)
```
- **Líneas 140-144:** Verifica que todas las predicciones sean 0 o 1.

```python
    def test_get_min_diff(self):
        row = pd.Series({"Fecha-O": "2017-01-01 23:45:00", "Fecha-I": "2017-01-01 23:30:00"})
        result = DelayModel._get_min_diff(row)
        assert result == 15.0
```
- **Líneas 146-153:** Prueba el cálculo de diferencia en minutos.

```python
    def test_preprocess_target_delay_values(self):
        features, target = self.model.preprocess(self.data, target_column="delay")
        unique_vals = set(target["delay"].unique())
        assert unique_vals.issubset({0, 1})
```
- **Líneas 155-159:** Verifica que el target solo contenga 0 y 1.

```python
    def test_model_persistence(self):
        features, target = self.model.preprocess(self.data, target_column="delay")
        self.model.fit(features, target)
        assert os.path.exists(DelayModel._MODEL_PATH)
        saved = joblib.load(DelayModel._MODEL_PATH)
        assert isinstance(saved, dict)
        assert "model" in saved
        assert "feature_columns" in saved
        new_model = DelayModel()
        new_model._load()
        feats = new_model.preprocess_api([{"OPERA": "Copa Air", "TIPOVUELO": "I", "MES": 10}])
        preds = new_model.predict(feats)
        assert isinstance(preds, list)
```
- **Líneas 161-182:** Verifica que `fit` guarde un diccionario y que `_load` restaure modelo y columnas.

```python
    def test_load_backward_compat(self):
        features, target = self.model.preprocess(self.data, target_column="delay")
        self.model.fit(features, target)
        joblib.dump(self.model._model, DelayModel._MODEL_PATH)
        new_model = DelayModel()
        new_model._load()
        assert new_model._model is not None
        assert new_model._feature_columns is None
```
- **Líneas 184-193:** Prueba compatibilidad con modelos guardados en formato antiguo.

```python
    def test_feature_columns_property_default(self):
        assert self.model.feature_columns == DelayModel.TOP_10_FEATURES
```
- **Líneas 195-197:** Verifica que la propiedad devuelva las features por defecto.

```python
    def test_feature_columns_property_custom(self):
        features, target = self.model.preprocess(self.data, target_column="delay")
        self.model.fit(features, target)
        assert self.model.feature_columns == self.FEATURES_COLS
```
- **Líneas 199-203:** Verifica que tras entrenar se guarden las columnas reales.

```python
    def test_train_from_csv(self):
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "data.csv")
        self.model.train_from_csv(csv_path)
        assert self.model._model is not None
        assert self.model._feature_columns is not None
        assert os.path.exists(DelayModel._MODEL_PATH)
```
- **Líneas 205-213:** Prueba el flujo completo de entrenamiento desde CSV.

```python
    def test_threshold_in_minutes(self):
        assert DelayModel.THRESHOLD_IN_MINUTES == 15
```
- **Líneas 215-217:** Verifica el umbral de retraso.

```python
    def test_get_period_day(self):
        assert DelayModel._get_period_day("2017-01-01 08:00:00") == "mañana"
        assert DelayModel._get_period_day("2017-01-01 12:00:00") == "tarde"
        assert DelayModel._get_period_day("2017-01-01 19:00:00") == "noche"
```
- **Líneas 219-230:** Prueba la clasificación de franjas horarias.

```python
    def test_is_high_season(self):
        assert DelayModel._is_high_season("2017-12-20 10:00:00") == 1
        assert DelayModel._is_high_season("2017-06-01 10:00:00") == 0
```
- **Líneas 232-241:** Prueba la detección de temporada alta.

```python
    def test_preprocess_generates_derived_columns(self):
        sample = self.data.head(10)
        features, target = self.model.preprocess(sample, target_column="delay")
        assert target.shape == (10, 1)
```
- **Líneas 243-249:** Verifica que el preprocesamiento genere el target para muestras pequeñas.

```python
    def test_predictions_match_ground_truth(self):
        features, target = self.model.preprocess(self.data, target_column="delay")
        x_train, x_test, y_train, y_test = train_test_split(features, target, test_size=0.33, random_state=42)
        self.model.fit(x_train, y_train)
        preds = self.model.predict(x_test)
        report = classification_report(y_test, preds, output_dict=True)
        assert report["1"]["recall"] > 0.60
        assert report["1"]["f1-score"] > 0.30
        assert report["0"]["f1-score"] > 0.50
        assert len(set(preds)) == 2
```
- **Líneas 251-265:** Valida predicciones contra etiquetas reales en split de entrenamiento/prueba.

```python
    def test_retrain_with_new_data(self):
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "data.csv")
        self.model.train_from_csv(csv_path)
        pred1 = self.model.predict(...)
        self.model.train_from_csv(csv_path)
        pred2 = self.model.predict(...)
        assert pred1 == pred2
```
- **Líneas 267-286:** Verifica que reentrenar con los mismos datos produce predicciones deterministas.

```python
    def test_varied_api_predictions(self):
        csv_path = ...
        self.model.train_from_csv(csv_path)
        flights = [6 vuelos variados]
        feats = self.model.preprocess_api(flights)
        preds = self.model.predict(feats)
        assert len(preds) == 6
        assert all(p in (0, 1) for p in preds)
```
- **Líneas 288-305:** Prueba que una lista variada de vuelos API genere predicciones binarias para cada uno.

---

## 13.14 `tests/stress/api_stress.py`

```python
from locust import HttpUser, task
```
- **Línea 1:** Importa las clases base de Locust.

```python
class StressUser(HttpUser):
```
- **Línea 3:** Define un usuario virtual de carga.

```python
    @task
    def predict_argentinas(self):
        self.client.post("/predict", json={"flights": [{"OPERA": "Aerolineas Argentinas", "TIPOVUELO": "N", "MES": 3}]})
```
- **Líneas 5-18:** Tarea que envía un request de predicción para Aerolineas Argentinas.

```python
    @task
    def predict_latam(self):
        self.client.post("/predict", json={"flights": [{"OPERA": "Grupo LATAM", "TIPOVUELO": "N", "MES": 3}]})
```
- **Líneas 21-34:** Tarea similar para Grupo LATAM. Ambas se ejecutan aleatoriamente según la carga configurada.

---

## 13.15 `tests/conftest.py`

```python
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
```
- **Líneas 1-3:** Cambia el directorio de trabajo al de `tests/` para que las rutas relativas a `../data/data.csv` resuelvan correctamente.

---

## 13.16 `.coveragerc`

```ini
[run]
source = challenge
omit = tests/*
```
- **Líneas 1-3:** Configura el análisis de cobertura sobre el paquete `challenge` y omite el directorio `tests`.

```ini
[report]
show_missing = true
```
- **Líneas 5-6:** En el reporte muestra las líneas que no tienen cobertura.

---

## 13.17 `README.md`

```markdown
# By Sayo
## ando codificando.. AI
### Software Engineer (ML & LLMs) Challenge, MLOps, DataScience, Statistic, ML and more....
```
- **Líneas 1-3:** Encabezado del proyecto.

```markdown
## Problem
```
- **Línea 5:** Sección que describe el problema.

```markdown
|Column|Description|
```
- **Líneas 8-27:** Tabla con las columnas originales del dataset y su significado.

```markdown
|`high_season`|1 if `Date-I` is between Dec-15 and Mar-3, or Jul-15 and Jul-31, or Sep-11 and Sep-30, 0 otherwise.|
|`min_diff`|difference in minutes between `Date-O` and `Date-I`|
|`period_day`|morning (between 5:00 and 11:59), afternoon (between 12:00 and 18:59) and night (between 19:00 and 4:59), based on `Date-I`.|
|`delay`|1 if `min_diff` > 15, 0 if not.|
```
- **Líneas 29-36:** Variables derivadas creadas por el Data Scientist.

---

# 14. Glosario de términos del proyecto

| Término | Significado |
|---------|-------------|
| `OPERA` | Nombre de la aerolínea operadora del vuelo. |
| `TIPOVUELO` | Tipo de vuelo: `I` internacional, `N` nacional. |
| `MES` | Mes programado del vuelo (1-12). |
| `delay` | Target binario: 1 si el retraso supera 15 minutos. |
| `min_diff` | Diferencia en minutos entre fecha real y programada. |
| `scale_pos_weight` | Peso de balanceo de XGBoost para clases desbalanceadas. |
| `one-hot encoding` | Transformación de categóricas a columnas binarias. |
| `TOP_10_FEATURES` | Conjunto fijo de 10 variables usadas por el modelo. |
| `model.pkl` | Artefacto serializado del modelo entrenado. |
| `Render` | Plataforma de despliegue en la nube usada en CD. |
| `Locust` | Herramienta de pruebas de carga. |
| `FastAPI` | Framework web para construir la API. |
