# Manual Técnico de Procesos — UC-326
## MAQRI: Motor de Refinamiento Iterativo de Consultas Aumentado por Memoria

**Versión:** 1.0  
**Área:** Ingeniería de Sistemas QBEX.ai / AnalitycsData.com / UTRON.ai / Arquitectura AGI  
**Aplicación:** UTRON.ai — Cerebro AGI multi-capa para trading y toma de decisiones autónoma  
**Objetivo del documento:** Especificar el Plan Maestro de Procesos (PMP), subprocesos, instructivos, plan de control y mapa de iteraciones del subsistema de memoria y búsqueda inteligente MAQRI, de forma que su arquitectura, mecanismos de auto-conciencia extendida, recuperación iterativa y gobernanza sean reproducibles, auditables y aptos para patente.

---

## 1. Alcance y objetivo

Este manual describe los procesos del subsistema MAQRI implementado en `/Users/utron/Documents/code-books/TomoIII/UC-326/code/`. Cubre:

- La indexación y recuperación de memoria episódica, semántica y procedimental.
- El refinamiento iterativo de consultas con aprendizaje de experiencias previas.
- La detección de redundancia y la divergencia forzada para evitar mínimos locales.
- La evaluación crítica de la calidad del retrieval (relevancia, cobertura, novedad).
- El cross-retrieval entre múltiples fuentes de memoria.
- La exposición de MAQRI como retriever inyectable para UC-325.
- La observabilidad, auditoría y trazabilidad del proceso de búsqueda inteligente.

**No se afirma conciencia subjetiva.** La "auto-conciencia extendida" aquí es un **modelo computacional observable** que registra experiencias, detecta patrones de éxito/fracaso y ajusta sus propias estrategias de búsqueda.

---

## 2. Glosario

| Término | Definición |
|---|---|
| **MAQRI** | Memory-Augmented Query Refinement Iterative. Motor de búsqueda que aprende de sus propios pasos intermedios. |
| **UC-326** | Capa de memoria y búsqueda inteligente del ecosistema AGI. |
| **UC-325** | Capa de razonamiento autorreflexivo; consume chunks refinados de UC-326. |
| **UC-315** | Cerebro AGI canónico; origina consultas y recibe respuestas. |
| **Memoria de Trabajo** | Estado de corto plazo de una tarea: objetivo, hechos acumulados, hipótesis activas, enfoques fallidos. |
| **Memoria Episódica** | Historial de experiencias de búsqueda: query, query refinado, documentos, score, información faltante, razón de fracaso. |
| **Memoria Semántica** | Base de conocimiento del dominio (simulación de vector DB). |
| **Memoria Procedimental** | Reglas heurísticas sobre cómo buscar, con aprendizaje de éxito. |
| **Retriever inyectable** | Buscador que UC-325 conecta/reemplaza como componente sin modificar el cerebro AGI. |
| **Critic** | Módulo evaluador que determina si los documentos recuperados responden la pregunta. |
| **Divergencia Forzada** | Transformación de una query para salir de un mínimo local de búsqueda. |
| **Cross-retrieval** | Recuperación simultánea en episódica + semántica + fuentes externas, con fusión. |
| **Fingerprint** | Hash SHA-256 normalizado para deduplicación de documentos. |
| **MP** | Macro Proceso. Proceso de alto nivel en el Plan Maestro de Procesos. |
| **SP** | Subproceso. Proceso detallado dentro de un MP. |
| **IT** | Instructivo de Trabajo. Procedimiento paso a paso para un rol operativo. |

---

## 3. Diagrama general de flujo

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ENTRADAS: query + contexto + dominio                  │
│     provenientes de UC-325 (reasoning loop) bajo solicitud de UC-315        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-01  RECEPCIÓN Y PARSEADO DE LA CONSULTA                                   │
│   UCMaqriLayer.retrieve_with_context(query, context, domain)                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-02  INICIALIZACIÓN DE MEMORIA DE TRABAJO                                  │
│   WorkingMemory(original_goal, accumulated_facts, hypotheses, failures)     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-03  BUCLE MAQRI ITERATIVO                                                  │
│   ┌───────────┐    ┌──────────┐    ┌────────┐    ┌──────────┐    ┌─────────┐  │
│   │ Verificar │───→│ Cross-   │───→│ Critic │───→│ Actualizar│───→│ Refinar │  │
│   │ redundancia│   │ retrieval│   │ evaluate│   │ memorias │   │ query   │  │
│   │ divergir  │    │          │    │        │    │          │    │         │  │
│   └───────────┘    └──────────┘    └────────┘    └──────────┘    └─────────┘  │
│   ↑________________________________________________________________________│
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-04  FUSIÓN, DEDUPLICACIÓN Y RANKING                                       │
│   CrossRetriever._deduplicate_and_rank(docs)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-05  SÍNTESIS Y ENTREGA DE RESULTADOS                                      │
│   MaqriResult: docs, iterations, episodes, working_memory, verdict           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-06  OBSERVABILIDAD Y TRAZABILIDAD                                         │
│   Métricas Prometheus + logs Loki + spans OpenTelemetry                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-07  EXPOSICIÓN COMO RETRIEVER INYECTABLE (API REST)                        │
│   /api/v1/maqri/search, /api/v1/maqri/refine, /api/v1/maqri/critic            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Plan Maestro de Procesos (PMP)

| ID | Macro Proceso | Responsable | Entradas principales | Salidas principales | KPIs |
|---|---|---|---|---|---|
| MP-01 | Recepción y parseo de la consulta | `UCMaqriLayer` | Query, contexto, dominio | Query normalizado, objetivo inicial | Latencia parseo, integridad de parámetros |
| MP-02 | Inicialización de memoria de trabajo | `MaqriEngine` | Objetivo, hipótesis, contexto | `WorkingMemory` inicializada | Campos inicializados |
| MP-03 | Bucle MAQRI iterativo | `MaqriEngine` | Query, memoria de trabajo, memoria episódica/semántica | Iteraciones, episodios, documentos candidatos | Iteraciones hasta convergencia, relevancia promedio, tasa de divergencia |
| MP-04 | Fusión, deduplicación y ranking | `CrossRetriever` | Documentos de múltiples fuentes | Documentos únicos ordenados por score | Tasa de deduplicación, ranking quality |
| MP-05 | Síntesis y entrega de resultados | `MaqriEngine` | Documentos únicos, episodios, memoria de trabajo | `MaqriResult` serializable | Final score, docs entregados, verdict |
| MP-06 | Observabilidad y trazabilidad | `ObservabilityManager` | Eventos del bucle | Métricas, logs, spans | Cobertura de trazas, latencias |
| MP-07 | Exposición como retriever inyectable | `api_326.py` | Peticiones REST | Respuestas JSON con INPUT/OUTPUT cards | Disponibilidad, latencia API, tasa de error |

---

## 5. Descripción de macro procesos y subprocesos

### MP-01 — Recepción y parseo de la consulta

**Propósito:** Recibir una consulta desde UC-325 (o directamente del cerebro AGI), normalizarla y preparar el contexto para el motor MAQRI.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/UC-326.py" />

**Entradas:**
- `query`: string con la consulta en lenguaje natural.
- `context`: contexto adicional de la tarea (opcional).
- `domain`: dominio del conocimiento (e.g., `trading`, `agi`, `reservations`).
- `max_iterations`: límite de iteraciones del bucle MAQRI (opcional).

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-01.1 | `receive_query()` | Recibe el query y valida que no sea vacío. | Query validado o error 400 |
| MP-01.2 | `normalize_query()` | Limpia espacios, mayúsculas y signos de puntuación excesivos. | Query normalizado |
| MP-01.3 | `select_configuration()` | Selecciona `MaqriConfig` según dominio si existe override. | Configuración activa |
| MP-01.4 | `create_trace_id()` | Genera UUID de traza para observabilidad end-to-end. | `trace_id` |

**Llamados a otras capas:**
- UC-325: origen del query.
- UC-315: origen indirecto vía UC-325.

**Salidas:**
- Query normalizado.
- Contexto y dominio.
- Configuración MAQRI activa.
- `trace_id`.

---

### MP-02 — Inicialización de memoria de trabajo

**Propósito:** Construir la memoria de trabajo de corto plazo que mantendrá el estado de la tarea durante la sesión MAQRI.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/maqri_models.py" />

**Entradas:**
- Query normalizado.
- Contexto.
- Hipótesis iniciales (opcional).

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-02.1 | `set_original_goal()` | Establece el objetivo original en `WorkingMemory`. | `original_goal` |
| MP-02.2 | `initialize_accumulated_facts()` | Inicializa hechos acumulados (vacío o sembrado con contexto). | `accumulated_facts` |
| MP-02.3 | `load_failed_approaches()` | Carga enfoques fallidos previos desde memoria episódica si aplica. | `failed_approaches` |
| MP-02.4 | `register_active_hypotheses()` | Registra hipótesis activas del contexto. | `active_hypotheses` |

**Llamados a otras capas:**
- UC-326 `EpisodicMemory`: lectura de fracasos previos.

**Salidas:**
- `WorkingMemory` inicializada.

---

### MP-03 — Bucle MAQRI iterativo

**Propósito:** Ejecutar iteraciones de búsqueda, evaluación y refinamiento hasta alcanzar confianza suficiente o agotar intentos.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/maqri_engine.py" />

**Entradas:**
- `WorkingMemory`.
- Memoria episódica, semántica, procedimental.
- `max_iterations`.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-03.1 | `check_redundancy()` | Verifica si la query actual es demasiado similar a las recientes en `EpisodicMemory`. | Flag `is_redundant` |
| MP-03.2 | `apply_divergence_strategy()` | Si hay redundancia, transforma la query con sinónimos, expansión, especialización o cambio de perspectiva. | Query divergente |
| MP-03.3 | `generate_query_variants()` | Genera variantes de query con memoria episódica, reglas procedimentales y expansiones estándar. | `List[QueryVariant]` |
| MP-03.4 | `cross_retrieve()` | Recupera documentos de memoria semántica, episódica y fuentes externas para cada variante. | Documentos candidatos |
| MP-03.5 | `critic_evaluate()` | Evalúa relevancia, cobertura y novedad; detecta información faltante y razón de fracaso. | `CriticAssessment` |
| MP-03.6 | `update_working_memory()` | Agrega hechos útiles y razones de fracaso a la memoria de trabajo. | `WorkingMemory` actualizada |
| MP-03.7 | `save_episode()` | Persiste la iteración en memoria episódica. | `SearchEpisode` |
| MP-03.8 | `refine_query_from_failure()` | Si no converge, usa `missing_info` y `failure_reason` para formular nueva query. | Query refinada |
| MP-03.9 | `check_convergence()` | Compara confianza contra `convergence_threshold` o verifica max iterations. | Veredicto de parada |

**Llamados a otras capas:**
- UC-326 `QueryRefiner326`: refinamiento.
- UC-326 `CrossRetriever`: búsqueda multi-fuente.
- UC-326 `CriticEvaluator`: evaluación de calidad.
- UC-326 `DivergenceStrategy`: divergencia forzada.

**Salidas:**
- Lista de `MaqriIteration`.
- Lista de `SearchEpisode`.
- Documentos candidatos acumulados.
- Veredicto de parada.

---

### MP-04 — Fusión, deduplicación y ranking

**Propósito:** Combinar documentos de múltiples fuentes, eliminar duplicados y ordenarlos por relevancia.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/cross_retriever.py" />

**Entradas:**
- Documentos de semántica, episódica y fuentes externas.
- Configuración de umbrales.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-04.1 | `normalize_scores_per_source()` | Ajusta scores por fuente para hacerlos comparables. | Scores normalizados |
| MP-04.2 | `deduplicate_by_fingerprint()` | Elimina documentos duplicados usando hash SHA-256 del contenido. | Conjunto de documentos únicos |
| MP-04.3 | `filter_by_minimum_relevance()` | Descarta documentos bajo `min_relevance_threshold`. | Documentos relevantes |
| MP-04.4 | `rank_by_score()` | Ordena documentos por score descendente. | Lista ordenada |
| MP-04.5 | `limit_results()` | Limita al top K configurado. | Resultado final listo para entrega |

**Llamados a otras capas:**
- UC-326 `SemanticMemory`, `EpisodicMemory`: fuentes de documentos.

**Salidas:**
- Lista ordenada de `RetrievedDocument`.

---

### MP-05 — Síntesis y entrega de resultados

**Propósito:** Empaquetar el resultado final con metadata completa para que UC-325 pueda consumirlo.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/maqri_models.py" />

**Entradas:**
- Documentos únicos ordenados.
- Iteraciones y episodios.
- `WorkingMemory` final.
- Veredicto de parada.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-05.1 | `compute_final_score()` | Toma la confianza de la última iteración como score final. | `final_score` |
| MP-05.2 | `compute_unique_facts()` | Extrae hechos únicos de la memoria de trabajo. | Número y lista de hechos únicos |
| MP-05.3 | `assemble_maqri_result()` | Construye `MaqriResult` serializable. | `MaqriResult` |
| MP-05.4 | `deliver_to_uc325()` | Entrega chunks en formato compatible con retriever de UC-325. | `List[Dict]` con content/source/score |

**Llamados a otras capas:**
- UC-325: consumidor del resultado.

**Salidas:**
- `MaqriResult` completo.
- Documentos como chunks para UC-325.

---

### MP-06 — Observabilidad y trazabilidad

**Propósito:** Registrar métricas, logs y trazas del proceso de búsqueda para auditoría y mejora continua.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/observability_326.py" />

**Entradas:**
- Eventos del bucle MAQRI.
- `trace_id`.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-06.1 | `start_root_span()` | Crea span principal con query y dominio. | Span raíz |
| MP-06.2 | `start_iteration_span()` | Crea span por iteración con query actual. | Span de iteración |
| MP-06.3 | `record_metrics()` | Incrementa contadores, histogramas y gauges. | Métricas Prometheus |
| MP-06.4 | `log_event()` | Escribe logs estructurados (INFO/ERROR) con trace_id. | Logs Loki-compatibles |
| MP-06.5 | `export_prometheus()` | Exporta métricas en formato Prometheus. | Endpoint `/metrics` |
| MP-06.6 | `close_spans()` | Cierra spans con estado OK/ERROR. | Trazas completas |

**Llamados a otras capas:**
- Sistema de observabilidad global (Prometheus, Loki, Grafana).

**Salidas:**
- Métricas, logs y spans.

---

### MP-07 — Exposición como retriever inyectable (API REST)

**Propósito:** Exponer MAQRI como servicio REST con INPUT/OUTPUT cards para integración con UC-325 u otros consumidores.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/api_326.py" />

**Entradas:**
- Peticiones HTTP/JSON.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-07.1 | `serve_health()` | Endpoint `/health`. | Estado del servicio |
| MP-07.2 | `serve_schema()` | Endpoint `/api/v1/schema` con INPUT/OUTPUT cards. | Documentación de API |
| MP-07.3 | `serve_maqri_search()` | Endpoint `/api/v1/maqri/search`. | `MaqriResult` JSON |
| MP-07.4 | `serve_maqri_documents()` | Endpoint `/api/v1/maqri/documents` para indexar documentos. | Confirmación de indexación |
| MP-07.5 | `serve_maqri_experience()` | Endpoint `/api/v1/maqri/experience` para agregar episodios. | Episodio guardado |
| MP-07.6 | `serve_maqri_critic()` | Endpoint `/api/v1/maqri/critic` para evaluar retrieval. | `CriticAssessment` JSON |
| MP-07.7 | `serve_maqri_refine()` | Endpoint `/api/v1/maqri/refine` para generar variantes. | Variantes de query |
| MP-07.8 | `serve_metrics()` | Endpoint `/metrics`. | Métricas Prometheus |

**Llamados a otras capas:**
- UC-325: cliente principal.
- UC-326 `UCMaqriLayer`: lógica de negocio.

**Salidas:**
- Respuestas JSON con INPUT/OUTPUT cards.

---

## 6. Componentes de memoria detallados

### Memoria Episódica

| Elemento | Descripción |
|---|---|
| `SearchEpisode` | Unidad de experiencia de búsqueda. |
| Campos | `episode_id`, `original_query`, `refined_query`, `retrieved_docs`, `relevance_score`, `missing_info`, `failure_reason`, `iteration`, `timestamp`, `success`. |
| Operaciones | `add()`, `find_similar()`, `is_redundant()`, `get_failed_strategies()`, `get_successful_queries()`, `get_lessons_learned()`, `get_statistics()`. |

### Memoria Semántica

| Elemento | Descripción |
|---|---|
| `SemanticMemory` | Base de conocimiento del dominio. |
| Operaciones | `add_document()`, `add_documents()`, `retrieve()`, `get_document_by_id()`, `get_sources()`, `get_stats()`, `reset()`. |
| Reemplazable | En producción se reemplaza por Pinecone, Milvus, FAISS, etc. |

### Memoria Procedimental

| Elemento | Descripción |
|---|---|
| `ProceduralMemory` | Reglas heurísticas sobre cómo refinar búsquedas. |
| Reglas por defecto | `low_results_expand`, `low_relevance_diverge`, `high_redundancy_specialize`, `broad_query_focus`, `specific_query_abstract`, `add_context`. |
| Aprendizaje | Cada regla acumula `hits` y `successes` para calcular `success_rate`. |

---

## 7. Instructivos de trabajo (IT)

### IT-01 — Cómo agregar documentos al conocimiento del dominio

1. Preparar lista de documentos con `content`, `source` y `metadata`.
2. Llamar `POST /api/v1/maqri/documents`.
3. Verificar `indexed` y `doc_ids` en la respuesta.
4. Opcional: validar con `GET /api/v1/maqri/stats`.

### IT-02 — Cómo ejecutar una búsqueda MAQRI

1. Construir payload JSON con `query`, `context`, `domain`, `max_iterations`.
2. Llamar `POST /api/v1/maqri/search`.
3. Revisar `verdict`, `final_score`, `total_docs`, `docs`.
4. Si `verdict == "insufficient_data"`, verificar logs en `/api/v1/maqri/logs`.

### IT-03 — Cómo registrar una experiencia de búsqueda

1. Llamar `POST /api/v1/maqri/experience` con `query`, `refined_query`, `relevance_score`, `missing_info`, `failure_reason`.
2. Verificar `episode_id` y `success`.
3. Usar `GET /api/v1/maqri/stats` para confirmar incremento en episodios.

### IT-04 — Cómo integrar UC-326 como retriever en UC-325

1. Importar `from uc326 import UCMaqriLayer`.
2. Instanciar `maqri = UCMaqriLayer(seed_kb=default_kb())`.
3. Pasar a `ReasoningLoopEngine(retriever=maqri)`.
4. Verificar que `UCMaqriLayer.retrieve(query, top_k, domain)` devuelve lista de dicts con `content`, `source`, `score`.

---

## 8. Plan de control y calidad

| Control | Responsable | Frecuencia | Criterio de aceptación |
|---|---|---|---|
| Validación operacional | Desarrollador | Cada cambio | `validate_uc326.py` 8/8 OK |
| Tests unitarios/integración | CI | Cada commit | 61 tests passed |
| Cobertura de endpoints API | QA | Semanal | Todos los endpoints responden 200/400 adecuadamente |
| Calidad de retrieval | Data Scientist | Mensual | Precision@K y recall sobre casos de test |
| Latencia | SRE | Continua | p95 < 500 ms por búsqueda |

---

## 9. Matriz de trazabilidad

| Requisito | Macro Proceso | Archivo | Test |
|---|---|---|---|
| Memoria episódica | MP-03 | `episodic_memory.py` | TestEpisodicMemory (7) |
| Memoria semántica | MP-03, MP-04 | `semantic_memory.py` | TestSemanticMemory (6) |
| Memoria procedimental | MP-03.3 | `procedural_memory.py` | TestProceduralMemory (5) |
| Divergencia forzada | MP-03.2 | `divergence_strategy.py` | TestDivergenceStrategy (4) |
| Refinamiento de queries | MP-03.3, MP-03.8 | `query_refiner_326.py` | TestQueryRefiner (6) |
| Evaluación Critic | MP-03.5 | `critic_evaluator.py` | TestCritic (4) |
| Cross-retrieval | MP-03.4, MP-04 | `cross_retriever.py` | TestCrossRetriever (3) |
| Motor MAQRI completo | MP-01 a MP-05 | `maqri_engine.py` | TestMaqriEngine (7) |
| Capa UC-326 | MP-01, MP-05 | `UC-326.py` | TestUCMaqriLayer (5) |
| API REST | MP-07 | `api_326.py` | TestAPI (8) |

---

## 10. Archivos y referencias

- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/maqri_models.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/episodic_memory.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/semantic_memory.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/procedural_memory.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/query_refiner_326.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/divergence_strategy.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/critic_evaluator.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/cross_retriever.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/maqri_engine.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/observability_326.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/UC-326.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/api_326.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/validate_uc326.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/code/tests_uc326/test_uc326.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-326/UC-326.md" />
