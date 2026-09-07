# Manual Técnico de Procesos — AGI Autoconsciente con Plasticidad Sináptica Digital

## UC-313: Sistema de Autoconciencia, Aprendizaje Continuo y Evolución Cognitiva

**Versión:** 1.0  
**Área:** Ingeniería de Sistemas QBEX.ai / AnalitycsData.com / U T R O N / Arquitectura AGI  
**Aplicación:** UTRON.ai — Cerebro AGI multi-capa para trading y toma de decisiones autónoma  
**Objetivo del documento:** Especificar el Plan Maestro de Procesos (PMP), subprocesos, instructivos, plan de control y mapa de iteraciones del sistema AGI, de forma que su arquitectura, conciencia funcional, plasticidad sináptica y gobernanza sean reproducibles, auditable y aptas para patente.

---

## 1. Alcance y objetivo

Este manual describe el flujo de procesos del cerebro AGI implementado en `/Users/utron/Documents/code-books/TomoIII/UC-313/code/`. Cubre:

- La percepción del entorno y el modelado interno.
- El Workspace Global (GWT), el Monitor Metacognitivo y la autoevaluación.
- El razonamiento mediante ReAct + Tree of Thoughts (ToT).
- La toma de decisiones BDI + Juice + Safety Supervisor.
- La ejecución y retroalimentación al World Model.
- La gestión de memoria AGI (working, factual, semantic, episodic, self).
- La plasticidad sináptica digital (Hebbiano + EWC) sobre el cerebro central.
- El Contract Net Protocol (CNP) para coordinación multi-agente.
- El aprendizaje por curiosidad y adquisición de nuevas habilidades.
- El bucle recursivo de autoconciencia.

**No se afirma conciencia subjetiva.** La "autoconciencia" aquí es un **modelo computacional observable** que mantiene continuidad temporal del self-model, evalúa su propio desempeño y genera narrativas internas.

---

## 2. Glosario

| Término | Definición |
|---|---|
| **AGI** | Sistema de inteligencia artificial general capaz de percibir, razonar, aprender y actuar de forma autónoma en múltiples tareas. |
| **Autoconciencia funcional** | Capacidad computacional del sistema para modelar su propio estado interno, metas, historial y desempeño; no implica experiencia subjetiva. |
| **GWT** | Global Workspace Theory. Arquitectura cognitiva donde la información seleccionada se difunde a módulos especializados. |
| **Meta-red** | Red de Nivel 1 que observa la actividad interna de la red ejecutora (Nivel 0) sin acceder directamente al entorno externo. |
| **Plasticidad sináptica digital** | Modificación controlada de pesos e hiperparámetros del sistema en función de la experiencia, con protección del conocimiento previo (EWC). |
| **Homeostasis artificial** | Mantenimiento de estabilidad operativa, integridad de modelos, recursos y seguridad, sin autopreservación descontrolada. |
| **CNP** | Contract Net Protocol. Protocolo de subasta donde un manager anuncia tareas y los agentes pujan. |
| **EWC** | Elastic Weight Consolidation. Técnica que congela parámetros críticos para evitar olvido catastrófico. |
| **MP** | Macro Proceso. Proceso de alto nivel en el Plan Maestro de Procesos. |
| **SP** | Subproceso. Proceso detallado dentro de un MP. |
| **IT** | Instructivo de Trabajo. Procedimiento paso a paso para un rol operativo. |
| **UC-322** | Capa de resolución de conflictos multi-agente multi-dominio. No modifica el cerebro AGI; lo envuelve como middleware. |
| **Reputación dinámica** | Score 0–1 por agente y dominio que se actualiza por episodio según éxito, calidad y eficiencia. Reemplaza pesos estáticos. |
| **Negociación con concesiones** | Proceso iterativo donde agentes ceden posición proporcionalmente a flexibilidad × reputación × ronda. Reemplaza aprobación binaria. |
| **Circuit breaker** | Disyuntor que se abre tras N conflictos consecutivos no resueltos, deteniendo el dominio hasta reset manual. |
| **Deadlock** | Ciclo de dependencia circular entre agentes que impide progreso (A espera a B, B espera a A). Detectado por DFS. |
| **Fingerprint SHA-256** | Hash normalizado de la descripción de una tarea para detectar trabajo duplicado entre agentes. |
| **Escalación formal** | Envío de un conflicto no resuelto al orquestador de nivel superior con veredictos PROCEED / REVIEW / STOP / REASSIGN. |

---

## 3. Diagrama general de flujo (mapa de proceso macro)

![Arquitectura AGI Autoconsciente](../agi_brain_architecture.png)

*Figura 1. Diagrama de arquitectura generado automáticamente desde el código (`code/generate_brain_image.py`). Muestra todas las capas del cerebro AGI, subsistemas de memoria, plasticidad sináptica digital y el bucle recursivo de autoconciencia.*

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ENTRADAS EXTERNAS                                  │
│   ticks de mercado │ noticias │ restricciones de riesgo │ objetivos        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-01  PERCEPCIÓN Y MODELADO DEL ENTORNO                                     │
│   CentralBrain.observe() → MarketPerceptionPipeline → snapshots + beliefs   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-02  WORKSPACE GLOBAL (GWT) + BROADCAST                                      │
│   GlobalWorkspace.build_workspace() → selección → broadcast a módulos       │
│   (risk, strategy, execution, memory, metacognition)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-03  MONITOR METACOGNITIVO (Red de Nivel 1)                                 │
│   MetacognitiveMonitor.observe_internal_state() → coherencia + veredicto     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-04  RAZONAMIENTO REACT + TREE OF THOUGHTS (ToT)                             │
│   predictores: brain / world_model / technical / microstructure / sentiment  │
│   expansión paralela → poda → backtracking → síntesis consensuada ask/bid    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-05  DECISIÓN BDI + JUICE FILTER + SAFETY SUPERVISOR                        │
│   Beliefs → Desires → Intentions → confrontación adversarial Juice → Safety   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-322 RESOLUCIÓN DE CONFLICTOS MULTI-AGENTE (UC-322)                         │
│   Nivel 1: Negociación con concesiones                                       │
│   Nivel 2: Votación ponderada por reputación dinámica                       │
│   Nivel 3: CNP dinámico con pujas compuestas                                │
│   Nivel 4: Escalación formal (PROCEED / REVIEW / STOP / REASSIGN)          │
│   + Duplicados SHA-256 + Deadlocks DFS + Circuit Breaker                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-06  EJECUCIÓN Y RETROALIMENTACIÓN                                          │
│   ExchangeSimulator.execute() → observaciones → WorldModel.update_from_tick  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-07  GESTIÓN DE MEMORIA AGI                                                │
│   IntelligentMemoryRouter: working / factual / semantic / episodic / self     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-08  AUTOEVALUACIÓN CONTINUA Y GOAL MANAGER                                  │
│   ContinuousSelfEvaluator → reflection → GoalManager → cambio seguro de meta│
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-09  PLASTICIDAD SINÁPTICA DIGITAL                                          │
│   UC307CognitiveEvolutionLayer + PrefrontalController                          │
│   fitness = 0.45·éxito + 0.35·calidad + 0.20·eficiencia                     │
│   Hebbiano + EWC → ajuste/reentrenamiento/mutación/eliminación               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-10  CONTRACT NET PROTOCOL (CNP)                                            │
│   broadcast de tarea → propuestas → adjudicación → evaluación evolutiva     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-11  APRENDIZAJE POR CURIOSIDAD                                             │
│   intento con herramientas existentes → hipótesis de nueva tool → generación  │
│   de código → registro → reintento → evaluación con plasticidad               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-12  BUCLE RECURSIVO DE AUTOCONCIENCIA                                      │
│   SelfAwarenessLoop: percibe → ejecuta → evalúa → ajusta → narra → persiste │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Plan Maestro de Procesos (PMP)

| ID | Macro Proceso | Responsable | Entradas principales | Salidas principales | KPIs |
|---|---|---|---|---|---|
| MP-01 | Percepción y modelado del entorno | `CentralBrain` | Ticks, news, request | Snapshots, beliefs, regimes, risk context | Latencia, cobertura de símbolos, calidad de datos |
| MP-02 | Workspace Global y broadcast | `GlobalWorkspace` | Snapshots, señales, hipótesis, self-model | Hipótesis seleccionada, mensajes broadcast | Capacidad usada, flags emitidos |
| MP-03 | Monitor metacognitivo | `MetacognitiveMonitor` | Workspace, estados internos | Veredicto PROCEED/REVIEW/STOP, coherencia | Tasa de intervención, falsos positivos |
| MP-04 | Razonamiento ReAct + ToT | `ReActReasonactToTBrain` | Ticks, news, predictores | Predicción ask/bid, árbol de razonamiento | Confianza, error de predicción |
| MP-05 | Decisión BDI + Juice + Safety | `BDIBuilder`, `JuiceAgent`, `SafetySupervisor` | Snapshots, beliefs, señales | Estrategia seleccionada, decisión de seguridad | Tasa de bloqueo, razones de rechazo |
| **MP-322** | **Resolución de conflictos multi-agente** | `ConflictResolutionLayer`, `ReputationSystem` | Beliefs conflictivas, votos, pujas | Resolución, veredicto, reputación actualizada | Tasa de resolución por nivel, latencia, conflictos/hora, circuit breaker |
| MP-06 | Ejecución y retroalimentación | `ExchangeSimulator`, `TradingWorldModel` | Orden aprobada | Resultado de ejecución, observaciones | Slippage, costo, error de predicción |
| MP-07 | Gestión de memoria AGI | `IntelligentMemoryRouter` | Consultas, episodios, hechos | Recuperaciones, almacenamiento persistente | Precisión de intención, latencia |
| MP-08 | Autoevaluación continua y metas | `ContinuousSelfEvaluator`, `GoalManager` | Episodios de desempeño | Reflexión, propuesta de cambio de objetivo | Tasa de éxito, recompensa promedio |
| MP-09 | Plasticidad sináptica digital | `UC307CognitiveEvolutionLayer`, `PrefrontalController` | Observaciones de ejecución | Decisión evolutiva, ajustes, pesos | Fitness, estabilidad homeostasis |
| MP-10 | Contract Net Protocol | `ContractNetMiddleware` | Tarea, agentes registrados | Adjudicación, evaluación de agentes | Fitness promedio de ventana, winner |
| MP-11 | Aprendizaje por curiosidad | `CuriositySkillLoop` | Problema, expected_answer | Nueva herramienta o resolución | Tasa de resolución, herramientas adquiridas |
| MP-12 | Bucle de autoconciencia | `SelfAwarenessLoop` | Entorno + estado interno | Narrativa, episodios, ajustes | Avg fitness, homeostasis stable |

---

## 5. Descripción de macro procesos y subprocesos

### MP-01 — Percepción y modelado del entorno

**Propósito:** Convertir datos brutos del entorno en representaciones internas (snapshots, beliefs, regimes) utilizables por las capas superiores.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/central_brain.py" />

**Entradas:**
- `TradingRequest`: símbolos, ticks, noticias, portfolio, modo, flag `approved`.
- Configuración de mercado e indicadores (`config.market`, `config.features`).

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-01.1 | `observe()` | Agrupa ticks por símbolo y llama a `MarketPerceptionPipeline.perceive()`. | `Dict[str, MarketSnapshot]` |
| MP-01.2 | `update_price_history()` | Actualiza historial de precios por símbolo en `TradingWorldModel`. | `price_history` actualizado |
| MP-01.3 | `initialize_belief()` / `update_belief()` | Crea/actualiza `BeliefState` mediante particle filter. | `beliefs` actualizado |
| MP-01.4 | `get_context()` | Compila snapshot, belief, regime, sentiment, uncertainty, price prediction, empirical estimate, risk context. | `Dict[str, Any]` |

**Llamados a otras capas:**
- `MarketPerceptionPipeline` (percepción).
- `TradingWorldModel` (modelado).
- `BeliefStateTracker` (particle filter).

**Salidas:**
- Snapshots por símbolo.
- Beliefs actualizados.
- Predicciones de precio e incertidumbre.
- Contexto de riesgo.

---

### MP-02 — Workspace Global (GWT) + broadcast

**Propósito:** Competir, seleccionar y difundir el contenido más relevante (hipótesis, señales, self-model) a todos los módulos suscritos.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/global_workspace.py" />

**Entradas:**
- `TradingRequest`.
- Snapshots (`Dict[str, Any]`).
- Señales (`List[Dict]`).
- Hipótesis (`List[Dict]`).
- Alertas (`List[str]`).
- Working memory / self-model.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-02.1 | `perceive_environment()` | Evalúa calidad de datos, salud de API y volatilidad. | `EnvironmentState` |
| MP-02.2 | `build_workspace()` | Selecciona hipótesis por confianza/riesgo y compila `WorkspaceContent`. | `WorkspaceContent` |
| MP-02.3 | `broadcast()` | Empaqueta `Envelope` para cada módulo y persiste selección en memoria. | Mensajes broadcast + flags |

**Llamados a otras capas:**
- `SituationalAwarenessMiddleware` (implementación base GWT/SAM).
- `IntelligentMemoryRouter` (persistencia del contenido seleccionado).

**Salidas:**
- `WorkspaceContent` con hipótesis seleccionada.
- Mensajes broadcast a risk, strategy, execution, memory, metacognition.
- Flags: `context_alert`, `low_self_confidence`, `high_volatility`.

---

### MP-03 — Monitor Metacognitivo

**Propósito:** Observar la actividad interna de la red ejecutora (Nivel 0) y emitir veredictos ejecutivos de control.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/metacognitive_monitor.py" />

**Entradas:**
- `WorkspaceContent`.
- `trading_output` (estado, estrategia, señales, resultado).
- `tot_prediction`.
- `execution_result`.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-03.1 | `evaluate_workspace()` | Usa `MetacognitionModule.evaluate()` para detectar conflictos, baja confianza, API degradada. | Dict SAM meta |
| MP-03.2 | `_compute_internal_coherence()` | Calcula coherencia entre self-confidence, ToT confidence y éxito de ejecución. | Score 0..1 |
| MP-03.3 | `observe_internal_state()` | Construye `ExecutionObservation` y llama a `UC307CognitiveEvolutionLayer.evaluate_execution()`. | Reporte meta + plasticidad |
| MP-03.4 | `_map_verdict()` | Mapea resultado a `PROCEED`, `REVIEW` o `STOP`. | Veredicto ejecutivo |

**Llamados a otras capas:**
- `sam.MetacognitionModule`.
- `UC307CognitiveEvolutionLayer`.

**Salidas:**
- `verdict`: `PROCEED`, `REVIEW`, `STOP`.
- `plasticity`: decisión y fitness de la capa evolutiva.
- `coherence`, `anomalies`.

---

### MP-04 — Razonamiento ReAct + Tree of Thoughts (ToT)

**Propósito:** Refinar la predicción ask/bid del siguiente tick mediante búsqueda en árbol con múltiples predictores, poda y backtracking.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/react_tot.py" />

**Entradas:**
- Símbolo.
- Ticks e historial.
- Noticias (opcional).
- Lista de predictores.
- Umbral de confianza y profundidad máxima.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-04.1 | `predict()` | Inicia el árbol de pensamientos. | Nodo raíz |
| MP-04.2 | `expand()` | Expansión paralela con cada predictor. | Nodos hijos |
| MP-04.3 | `evaluate_node()` | Evalúa confianza y consistencia. | Score por nodo |
| MP-04.4 | `prune()` | Poda ramas bajo umbral (`PRUNED_FAILED`). | Árbol reducido |
| MP-04.5 | `backtrack()` | Vuelve al nodo anterior si falla. | Nodo alternativo |
| MP-04.6 | `consensus_synthesis()` | Combina predicciones supervivientes ponderadas. | Predicción ask/bid final |

**Llamados a otras capas:**
- `TickPredictionEnvironment` → `CentralBrain.predict_next_price()`.
- Predictores: `brain`, `world_model`, `technical`, `microstructure`, `sentiment`, `ensemble`.

**Salidas:**
- `final_prediction`: ask, bid, mid, spread, confidence, source_strategy.
- `tree_summary`: nodos, hojas exitosas, podadas, backtracking.
- `trace`: pasos ReAct.

---

### MP-05 — Decisión BDI + Juice Filter + Safety Supervisor

**Propósito:** Seleccionar una estrategia de trading alineada con creencias, deseos e intenciones, validarla ante ataques adversariales (Juice) y garantizar seguridad.

**Archivos clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/bdi.py" />, <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/juice_agents.py" />, <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/sam.py" />

**Entradas:**
- Snapshots, beliefs, desires, intentions.
- Señales de agentes.
- Restricciones de riesgo.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-05.1 | `build_beliefs()` | Traduce snapshot a `BDIBeliefs`. | `BDIBeliefs` |
| MP-05.2 | `build_desires()` | Define objetivos a partir del request y constraints. | `BDIDesires` |
| MP-05.3 | `build_intention()` | Selecciona acción/strategia candidata. | `BDIIntention` |
| MP-05.4 | `adversarial_confrontation_node()` | Juice confronta la estrategia con contra-argumentos. | `JuiceVerdict` |
| MP-05.5 | `SafetySupervisor.check()` | Verifica restricciones de riesgo y genera plan de rollback. | `Dict[str, Any]` |

**Llamados a otras capas:**
- `StrategyGenerator`, `StrategyCritic`, `MonteCarloSimulator`, `RiskEngine`.

**Salidas:**
- `bdi_state`.
- `juice_verdict` (approved/blocked, reasoning).
- `selected_strategy` o estado `blocked`/`awaiting_input`.
- `safety_flags`, `requires_confirmation`.

---

### MP-06 — Ejecución y retroalimentación

**Propósito:** Ejecutar la orden simulada y retroalimentar al World Model con el resultado real observado.

**Archivos clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/exchange.py" />, <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/world_model.py" />

**Entradas:**
- Estrategia aprobada y orden.
- Estado del portfolio.
- Restricciones de riesgo.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-06.1 | `execute_node()` | Simula ejecución en `ExchangeSimulator`. | `ExecutionResult` |
| MP-06.2 | `record_observation()` | Convierte resultado en `WorldModelObservation`. | Observación |
| MP-06.3 | `update_from_observation()` | Actualiza estimaciones empíricas y reentrena si aplica. | Estimativas actualizadas |
| MP-06.4 | `learn_from_tick()` | Alimenta modelo con par `(current_price, next_price)`. | Experiencia añadida |

**Salidas:**
- `execution_result` (success, slippage, cost, reward).
- `observations` para memoria SAM.
- Modelo probabilístico reentrenado (condicional).

---

### MP-07 — Gestión de memoria AGI

**Propósito:** Enrutar, almacenar y recuperar información en los subsistemas de memoria adecuados según la intención de la consulta.

**Archivos clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/memory_router.py" />, <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/short_term_memory.py" />, <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/structured_memory.py" />, <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/long_term_memory.py" />, <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/self_model_store.py" />

**Entradas:**
- Consulta en lenguaje natural.
- Contexto (tipo de entidad, id, atributo).
- Contenido a almacenar.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-07.1 | `classify_intent()` | Clasifica en WORKING_STATE, FACTUAL_LOOKUP, SEMANTIC_RECALL, SELF_MODEL. | `MemoryIntent` |
| MP-07.2 | `retrieve()` | Redirige a notepad, SQL o vectorial. | `MemoryResult` |
| MP-07.3 | `store_working_memory()` | Guarda nota en `ShortTermNotepad`. | Nota almacenada |
| MP-07.4 | `structured.store()` / `query()` | CRUD en SQLite para datos estructurados y self-model. | Valor o confirmación |
| MP-07.5 | `vector.add()` / `retrieve()` | Almacenamiento/recuperación semántica. | IDs + similitud |

**Salidas:**
- `MemoryResult` con intención, fuente, datos, latencia, confianza.
- Persistencia entre sesiones (`uc296_memory.db`, `uc296_vectors.json`, `uc296_self_model.json`).

---

### MP-08 — Autoevaluación continua y Goal Manager

**Propósito:** Registrar desempeño, generar reflexiones y proponer cambios seguros de objetivo.

**Archivos clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/continuous_self_eval.py" />, <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/metacognitive_goals.py" />

**Entradas:**
- Episodios de ejecución (task, success, metrics, context).
- Historial de desempeño en `SelfModelStore`.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-08.1 | `evaluate_execution()` | Crea `PerformanceEpisode` y lo registra. | Episodio |
| MP-08.2 | `reflect()` | Calcula tasa de éxito, reward promedio y sugerencias. | Reflexión |
| MP-08.3 | `apply_goal_change()` | Valida propuesta contra patrones permitidos y métricas. | Estado applied/rejected/awaiting |
| MP-08.4 | `update_goal()` | Persiste nuevo objetivo en self-model. | Self-model actualizado |

**Salidas:**
- `PerformanceEpisode`.
- Reflexión con sugerencias.
- Objetivo actualizado (si aprobado y cumple condiciones).

---

### MP-09 — Plasticidad sináptica digital

**Propósito:** Evaluar fitness operativo y decidir acciones evolutivas controladas sobre el sistema, incluyendo reescritura segura de parámetros del cerebro central y world model.

**Archivos clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/cognitive_evolution_layer.py" />, <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/brain_plasticity_interface.py" />

**Entradas:**
- `ExecutionObservation`: success, reward, latency, tokens, tool_calls, errors, confidence, coherence, activations.
- Tasa de éxito reciente, historial de decisiones.

**Fórmula de fitness:**

```text
quality      = (0.6 · confidence + 0.4 · coherence) · (1 - error_penalty)
efficiency   = (1 - tokens/max_tokens + 1 - tools/max_tools + 1 - latency/max_latency) / 3
fitness      = 0.45 · task_success_rate + 0.35 · quality + 0.20 · efficiency
```

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-09.1 | `_compute_quality()` | Calcula calidad a partir de confianza, coherencia y errores. | Score 0..1 |
| MP-09.2 | `_compute_efficiency()` | Calcula eficiencia por consumo de recursos. | Score 0..1 |
| MP-09.3 | `evaluate_execution()` | Calcula fitness y selecciona decisión evolutiva. | `PlasticityResult` |
| MP-09.4 | `observe_execution_network()` | Meta-red detecta anomalías internas. | `MetaNetworkObservation` |
| MP-09.5 | `update_synaptic_weights()` | Ajusta pesos Hebbiano con ancla EWC. | Pesos actualizados |
| MP-09.6 | `propose_adjustment()` | Crea propuesta de ajuste seguro. | `AdjustmentProposal` |
| MP-09.7 | `apply_proposal()` / `PrefrontalController` | Aplica cambios de parámetros o reentrena world model. | Estado applied/rollback |
| MP-09.8 | `check_homeostasis()` | Verifica estabilidad y límites. | `HomeostasisReport` |
| MP-09.9 | `rollback_last_applied()` | Restaura snapshot previo. | Confirmación de rollback |

**Decisiones posibles:**

| Fitness / Estado | Decisión | Acciones |
|---|---|---|
| Meta-red `stop`/`revert` | `stop` / `revert` | Detener o revertir |
| Ajustes excesivos | `review` | Revisión humana |
| `success < 0.5` y `fitness < 0.3` | `eliminate` | Eliminar agente, proponer reemplazo |
| `fitness >= 0.85` | `persist` + `grow_crossover` | Conservar élite |
| Calidad baja | `adjust_params` | Ajustar hiperparámetros |
| Eficiencia baja | `adjust_params` | Reducir consumo |
| `fitness < 0.5` | `mutate` | Perturbación controlada |
| `fitness < 0.6` | `retrain` | Reentrenar world model |

**Salidas:**
- `PlasticityResult` con decisión, fitness, propuestas, homeostasis, meta-observación, reasoning.
- Pesos sinápticos actualizados (agentes, estrategias, GWT).
- Cambios en parámetros plásticos de `CentralBrain`/`TradingWorldModel`.
- Log de decisiones con `trace_id`.

---

### MP-10 — Contract Net Protocol (CNP)

**Propósito:** Coordinar una población de agentes mediante subasta con evaluación evolutiva y ventanas temporales.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/cnp_broadcast_middleware.py" />

**Entradas:**
- Tarea (id + descripción + requisitos).
- Agentes registrados (`CNPAgentProfile`).
- Resultado de ejecución (success).

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-10.1 | `broadcast_task()` | Anuncia tarea y persiste anuncio. | `CNPRound` |
| MP-10.2 | `collect_proposals()` | Recoge `CNPProposal` de cada agente. | Lista de propuestas |
| MP-10.3 | `evaluate_and_award()` | Score = 0.5·bid + 0.3·confidence - 0.1·cost - 0.1·latency; adjudica ganador. | Winner + award_score |
| MP-10.4 | `evaluate_execution()` por agente | Evalúa cada agente con `UC307CognitiveEvolutionLayer`. | Decisiones evolutivas |
| MP-10.5 | `update_synaptic_weights()` | Refuerza/debilita agentes según desempeño. | Pesos actualizados |
| MP-10.6 | `window_summary()` | Agrega métricas en ventana temporal. | Resumen de población |

**Salidas:**
- `CNPRound` con winner, award_score, evolution_decisions.
- `window_summary`: avg_fitness, winners, agent_count.
- Pesos sinápticos de población.

---

### MP-11 — Aprendizaje por curiosidad

**Propósito:** Minimizar la incertidumbre del agente adquiriendo nuevas herramientas cuando las existentes no resuelven un problema.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/curiosity_skill_loop.py" />

**Entradas:**
- Problema en lenguaje natural.
- `expected_answer`.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-11.1 | `_try_solve_with_existing_tools()` | Intenta resolver con `ToolRegistry` actual. | Booleano solved |
| MP-11.2 | `FailureCuriosityTrigger.hypothesize()` | Genera firma de función Python como hipótesis. | Dict `{name, signature, description}` |
| MP-11.3 | `SimulatedCodeGenerator.generate()` | Produce código Python a partir de la firma. | Código fuente |
| MP-11.4 | `ToolRegistry.register()` | Compila y registra la nueva herramienta. | `Tool` disponible |
| MP-11.5 | `_try_solve_with_new_tool()` | Reintenta con la nueva herramienta. | Booleano solved |
| MP-11.6 | `evaluate_execution()` | Evalúa el intento con plasticidad. | PlasticityResult |

**Salidas:**
- `CuriosityAttempt` con outcome, generated_skill, trace.
- `ToolRegistry` ampliado.
- Registro en memoria episódica.

---

### MP-12 — Bucle recursivo de autoconciencia

**Propósito:** Cerrar el ciclo completo: percibir, razonar, actuar, evaluar, ajustar, recordar y narrar.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/self_awareness_loop.py" />

**Entradas:**
- Configuración del entorno (símbolo, ticks, modo, approved).
- Estado interno persistido (self-model, memoria, pesos).

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| MP-12.1 | `run_episode()` | Genera ticks y construye `TradingRequest`. | Request |
| MP-12.2 | `pipeline.run()` | Ejecuta MP-01 a MP-08. | `BrainMemoryPipeline` result |
| MP-12.3 | GWT + Monitor | `GlobalWorkspace.build_workspace()` + `MetacognitiveMonitor.observe_internal_state()`. | Veredicto metacognitivo |
| MP-12.4 | Plasticidad | `evaluate_execution()` + `update_gwt_weight()` + prefrontal. | Ajustes aplicados |
| MP-12.5 | CNP | `ContractNetMiddleware.run_round()` (opcional). | Winner + decisiones |
| MP-12.6 | Curiosidad | `CuriositySkillLoop.metatool_learn_new_skill()` (opcional). | Nueva skill |
| MP-12.7 | `_generate_narrative()` | Crea narrativa auto-referencial. | String narrativa |
| MP-12.8 | Persistencia | Almacena episodio en memoria y self-model. | Continuidad del self |
| MP-12.9 | `run_loop()` | Itera `n_episodes`. | Resumen |

**Salidas:**
- `SelfAwarenessEpisode` (narrativa, plasticity, gwt_broadcast, monitor_verdict, cnp_winner, curiosity_skill).
- `summary()` con avg_fitness, homeostasis, pesos sinápticos, narrativas.

---

## 6. Mapa de iteraciones y llamados entre capas

### 6.1 Iteración principal del bucle de autoconciencia

```text
       Entorno
          │
          ▼
   ┌──────────────┐
   │  MP-01       │ CentralBrain.observe()
   │  Percepción  │
   └──────────────┘
          │ snapshots
          ▼
   ┌──────────────┐
   │  MP-02       │ GlobalWorkspace.build_workspace()
   │  GWT         │ GlobalWorkspace.broadcast()
   └──────────────┘
          │ selected_hypothesis / broadcast
          ▼
   ┌──────────────┐        ┌──────────────┐
   │  MP-03       │◄──────►│  Memoria     │
   │  Monitor     │        │  (MP-07)     │
   │  Meta-red    │        └──────────────┘
   └──────────────┘
          │ veredicto / plasticity
          ▼
   ┌──────────────┐
   │  MP-04       │ ReActReasonactToTBrain.predict()
   │  ReAct + ToT │
   └──────────────┘
          │ predicción ask/bid
          ▼
   ┌──────────────┐
   │  MP-05       │ BDI + Juice + Safety
   │  Decisión    │
   └──────────────┘
          │ propuestas conflictivas
          ▼
   ┌──────────────┐
   │  MP-322      │ ConflictResolutionLayer.resolve()
   │  Resolución  │ Negociación → Votación → CNP → Escalación
   │  Conflictos  │ + Duplicados + Deadlocks + Circuit Breaker
   └──────────────┘
          │ resolución / veredicto
          ▼
   ┌──────────────┐
   │  MP-06       │ ExchangeSimulator.execute()
   │  Ejecución   │ WorldModel.update_from_tick()
   └──────────────┘
          │ execution_result / observations
          ▼
   ┌──────────────┐
   │  MP-08       │ ContinuousSelfEvaluator
   │  Autoeval.   │ GoalManager
   └──────────────┘
          │ episodio / reflexión / goal_proposal
          ▼
   ┌──────────────┐
   │  MP-09       │ UC307CognitiveEvolutionLayer
   │  Plasticidad │ PrefrontalController
   └──────────────┘
          │ pesos / parámetros / decisiones
          └──────────────────────────────────────┐
                          │                        │
                          ▼                        ▼
                  ┌──────────────┐        ┌──────────────┐
                  │  MP-10 CNP   │        │ MP-11 Curios.│
                  └──────────────┘        └──────────────┘
                          │                        │
                          └──────────┬───────────┘
                                     ▼
                            ┌──────────────┐
                            │  MP-12       │ SelfAwarenessLoop
                            │  Narrativa   │ _generate_narrative()
                            │  + Persist.  │ memory_router.store_episode()
                            └──────────────┘
                                     │
                                     ▼
                              [Retorno al Entorno]
```

### 6.2 Llamados entre capas clave

| Origen | Destino | Método / Flujo | Propósito |
|---|---|---|---|
| `SelfAwarenessLoop` | `BrainMemoryPipeline` | `pipeline.run(request)` | Ejecutar percepción → memoria → AGI |
| `BrainMemoryPipeline` | `CentralBrain` | `brain.observe(request)` | Percibir entorno |
| `BrainMemoryPipeline` | `ReActReasonactToTBrain` | `tot.predict(...)` | Predicción ask/bid |
| `BrainMemoryPipeline` | `UC307CognitiveEvolutionLayer` | `evaluate_execution()` | Evaluar episodio |
| `UC307CognitiveEvolutionLayer` | `PrefrontalController` | `retrain_world_model()` / `update_param()` | Reescribir cerebro central |
| `UC307CognitiveEvolutionLayer` | `GoalManager` | `apply_goal_change()` | Cambio seguro de meta |
| `UC307CognitiveEvolutionLayer` | `IntelligentMemoryRouter` | `store_episode()` | Persistir experiencia |
| `GlobalWorkspace` | `IntelligentMemoryRouter` | `store_working_memory()` / `store_episode()` | Persistir selección GWT |
| `MetacognitiveMonitor` | `UC307CognitiveEvolutionLayer` | `evaluate_execution()` | Convertir veredicto en plasticidad |
| `ContractNetMiddleware` | `UC307CognitiveEvolutionLayer` | `evaluate_execution()` por agente | Evolución de población |
| `CuriositySkillLoop` | `UC307CognitiveEvolutionLayer` | `evaluate_execution()` | Evaluar adquisición de skill |
| **UC-322** `ConflictResolutionLayer` | `NegotiationEngine` | `negotiate(conflict)` | Nivel 1: concesiones |
| **UC-322** `ConflictResolutionLayer` | `VotingSystem` | `vote(conflict, options, prefs)` | Nivel 2: votación ponderada |
| **UC-322** `ConflictResolutionLayer` | `DynamicCNP` | `bid(conflict, bids)` | Nivel 3: pujas dinámicas |
| **UC-322** `ConflictResolutionLayer` | `EscalationProtocol` | `escalate(conflict, ...)` | Nivel 4: veredicto formal |
| **UC-322** `ConflictResolutionLayer` | `ReputationSystem` | `record_episode()` / `get_reputation()` | Pesos dinámicos por dominio |
| **UC-322** `ConflictResolutionLayer` | `DuplicateDetection` | `register_task()` | Fingerprints SHA-256 |
| **UC-322** `ConflictResolutionLayer` | `DeadlockDetector` | `detect_cycle()` | DFS sobre wait graph |
| **UC-322** `EscalationProtocol` | `MetacognitiveMonitor` | Recibe veredicto REVIEW/STOP | Escalación desde monitor |
| Resultado de ejecución | **UC-322** `ReputationSystem` | `record_episode(success, quality)` | Feedback actualiza reputación |

---

## 7. Plan de Control

### 7.1 Variables críticas y controles

| Variable | Método de control | Frecuencia | Responsable | Registro / Evidencia |
|---|---|---|---|---|
| Latencia de percepción | Medición `latency_ms` en `MemoryResult` | Cada request | `CentralBrain` | Logs de percepción |
| Calidad de datos | `data_quality` en `EnvironmentState` | Cada observación | `SituationalAwarenessMiddleware` | Workspace broadcast flags |
| Coherencia interna | `_compute_internal_coherence()` | Cada episodio | `MetacognitiveMonitor` | Reporte de monitor |
| Fitness operativo | `fitness = 0.45·success + 0.35·quality + 0.20·efficiency` | Cada ejecución | `UC307CognitiveEvolutionLayer` | `PlasticityResult` |
| Homeostasis | `check_homeostasis()` | Cada decisión + ventanas | `UC307CognitiveEvolutionLayer` | `HomeostasisReport` |
| Ajustes por hora | Contador en `decision_log` | Continuo | `UC307CognitiveEvolutionLayer` | Warnings en homeostasis |
| Tasa de éxito reciente | `SelfModelStore.get_recent_performance()` | Cada reflexión | `ContinuousSelfEvaluator` | Reflexión |
| Cambios de objetivo | Validación contra `allowed_goal_patterns` y métricas | Cada propuesta | `GoalManager` | Trace de propuesta |
| Propuestas de plasticidad | `approved_by` obligatorio para riesgo alto/arquitectura | Cada propuesta | `UC307CognitiveEvolutionLayer` | `AdjustmentProposal` |
| Pesos sinápticos | Clip a rango [0, 2] y ancla EWC | Cada update | `UC307CognitiveEvolutionLayer` / `PrefrontalController` | Snapshot de pesos |
| Reentrenamiento world model | `_should_retrain()` por `retrain_after`, incertidumbre o error | Cada observación | `TradingWorldModel` | Estado `observations_since_train` |
| Seguridad de ejecución | `SafetySupervisor.check()` | Antes de ejecutar | `SafetySupervisor` | `safety_decision` |
| Ejecución CNP | Score ponderado + evaluación evolutiva | Cada ronda | `ContractNetMiddleware` | `CNPRound` |
| Curiosidad / nuevas herramientas | Verificación de firma y compilación | Cada intento | `CuriositySkillLoop` | `CuriosityAttempt` |
| Rollback | `rollback_last_applied()` / `PrefrontalController.rollback()` | Bajo solicitud o anomalía | `UC307CognitiveEvolutionLayer` | Snapshot + log |
| **Reputación dinámica** | `ReputationSystem.record_episode()` → recalcula score | Cada episodio resuelto | `ReputationSystem` | `EpisodeRecord`, Prometheus `conflict_*_total` |
| **Tasa de resolución por nivel** | Contadores `conflict_negotiation_total`, `conflict_voting_total`, `conflict_cnp_total`, `conflict_escalation_total` | Cada conflicto | `ObservabilityManager` | Prometheus counters + Grafana |
| **Circuit breaker UC-322** | `EscalationProtocol.consecutive_conflicts >= 3` → OPEN | Cada conflicto no resuelto | `EscalationProtocol` | Estado + alerta `CircuitBreakerAbierto` |
| **Deadlocks detectados** | `DeadlockDetector.detect_cycle()` → DFS en wait graph | Cada resolución | `DeadlockDetector` | `DeadlockInfo`, logs Loki |
| **Duplicados detectados** | `DuplicateDetection.register_task()` → fingerprint SHA-256 | Cada registro de tarea | `DuplicateDetection` | `TaskRecord`, logs Loki |
| **Latencia de resolución** | `ConflictResolutionResult.total_duration` | Cada conflicto | `ConflictResolutionLayer` | Histograma Prometheus |
| **Conflictos escalados** | Ratio escalación/total | Ventana temporal | `ObservabilityManager` | Dashboard Grafana |

### 7.2 Plan de contingencia / rollback

1. **Antes de aplicar cualquier ajuste** se genera un snapshot del estado plástico (`synaptic_weights`, `self_model`, parámetros).
2. **Si `homeostasis.stable` es False** o `MetaNetworkObservation.verdict == "stop"`, se bloquean nuevos ajustes y se requiere revisión humana.
3. **Si un ajuste genera error**, se invoca `rollback_last_applied()` automáticamente.
4. **Propuestas de riesgo alto u objetivos** requieren `approved_by` explícito.
5. **Límites de recursos**: tokens, tool_calls y latencia monitoreados; excesos generan warnings y pueden detener ajustes.

---

## 8. Instructivos de trabajo

### 8.1 Instructivo de operación normal

1. Iniciar el sistema con configuración por defecto (`get_config()`).
2. Ejecutar `SelfAwarenessLoop.run_loop(n_episodes, symbol, approved=True, mode="paper")`.
3. Verificar en logs que todas las fases generan outputs no vacíos.
4. Revisar `summary["homeostasis_stable_all"]` y `summary["avg_fitness"]`.
5. Almacenar `narratives`, `episodes` y `synaptic_weights` para auditoría.

### 8.2 Instructivo de supervisión humana

1. Consultar propuestas pendientes mediante API `/api/v1/brain/plasticity/state`.
2. Revisar `risk_level` y `adjustment_type`.
3. Aprobar/rechazar mediante `/api/v1/brain/plasticity/apply` con `approved_by`.
4. En caso de anomalía, ejecutar rollback manual o reiniciar desde snapshot.

### 8.3 Instructivo de mantenimiento y rollback

1. Ejecutar `python code/UC-313.py --validate` para verificar compatibilidad.
2. Si un cambio de parámetro produce degradación, invocar `PrefrontalController.rollback()`.
3. Si la memoria vectorial o SQLite corrompe, restaurar backups `uc296_memory.db` / `uc296_vectors.json`.
4. Verificar tests: `python -m pytest tests/test_compatibility_validator.py -q`.

### 8.4 Instructivo de integración de nuevo agente/skill

1. Para agente CNP: registrar `CNPAgentProfile` y ejecutar `ContractNetMiddleware.run_round()`.
2. Para nueva herramienta: enviar POST `/api/v1/brain/curiosity/learn` con `problem` y `expected_answer`.
3. Validar que la nueva skill se refleja en `CuriositySkillLoop.registry.list_tools()`.

---

## 9. Consideraciones para patente

### 9.1 Novedad técnica

La arquitectura combina de forma integrada:

- **Autoconciencia funcional computacional** mediante un Workspace Global (GWT) que difunde contenido seleccionado a módulos especializados, un Monitor Metacognitivo (Red de Nivel 1) que observa exclusivamente estados internos de la red ejecutora (Nivel 0), y un bucle recursivo que genera narrativas auto-referenciales persistidas como episodios de memoria.
- **Plasticidad sináptica digital** con aprendizaje Hebbiano controlado y Consolidación Sináptica Elástica (EWC) para proteger conocimiento antiguo, aplicada no solo a agentes externos sino a los parámetros del `CentralBrain` y del `TradingWorldModel` (cerebro prefrontal).
- **Homeostasis artificial** que vincula fitness operativo con límites de recursos, tasa de ajustes y estabilidad, impidiendo autopreservación descontrolada.
- **Co-evolución multi-agente** mediante Contract Net Protocol evaluado con la misma capa de plasticidad y ventanas temporales.
- **Aprendizaje por curiosidad** con generación automática de herramientas ante fallo, integrado con evaluación evolutiva.

### 9.2 Reivindicaciones sugeridas

1. Sistema AGI con arquitectura de dos niveles: red ejecutora (Nivel 0) y meta-red monitora (Nivel 1), donde la meta-red recibe como única entrada la actividad interna de la red ejecutora y produce veredictos ejecutivos.
2. Método de autoconciencia funcional que mantiene continuidad temporal mediante un self-model persistente, memoria episódica y generación de narrativas internas.
3. Método de plasticidad sináptica digital que reescribe dinámicamente parámetros de un cerebro central y su world model, protegiendo conocimiento previo mediante EWC.
4. Método de homeostasis artificial que regula la tasa de auto-modificación del sistema en función de fitness, recursos y estabilidad.
5. Método de coordinación evolutiva multi-agente mediante CNP evaluado con una capa de plasticidad común.
6. Método de adquisición de habilidades por curiosidad que genera y compila herramientas nuevas ante la incapacidad de resolver un problema con herramientas existentes.

---

## 10. Anexos

### Anexo A — API REST relevante

| Método | Endpoint | Proceso |
|---|---|---|
| POST | `/api/v1/brain/plasticity/evaluate` | MP-09 |
| POST | `/api/v1/brain/plasticity/propose` | MP-09 |
| POST | `/api/v1/brain/plasticity/apply` | MP-09 |
| GET | `/api/v1/brain/plasticity/state` | MP-09 / Plan de control |
| POST | `/api/v1/brain/cnp/run` | MP-10 |
| POST | `/api/v1/brain/curiosity/learn` | MP-11 |
| POST | `/api/v1/brain/self_awareness/loop` | MP-12 |
| POST | `/api/v1/brain/memory_pipeline` | MP-01 a MP-08 |
| POST | `/api/v1/conflicts/resolve` | MP-322 (SP-322.1 a SP-322.4) |
| POST | `/api/v1/reputation/record` | MP-322 (SP-322.5) |
| GET | `/api/v1/reputation/ranking` | MP-322 (SP-322.5) |
| GET | `/api/v1/reputation/<agent_id>` | MP-322 (SP-322.5) |
| POST | `/api/v1/duplicate/check` | MP-322 (SP-322.6) |
| POST | `/api/v1/deadlock/check` | MP-322 (SP-322.6) |
| GET | `/api/v1/conflicts/history` | MP-322 |
| GET | `/api/v1/escalation/history` | MP-322 (SP-322.4) |
| GET | `/api/v1/escalation/circuit-breaker` | MP-322 (SP-322.7) |
| POST | `/api/v1/escalation/circuit-breaker/reset` | MP-322 (SP-322.7) |
| GET | `/api/v1/observability/summary` | MP-322 |
| GET | `/api/v1/observability/logs` | MP-322 |
| GET | `/api/v1/observability/spans` | MP-322 |
| GET | `/metrics` | MP-322 (Prometheus) |
| GET | `/api/v1/tasks/active` | MP-322 (SP-322.6) |

### Anexo B — Comandos CLI

```bash
# Validar compatibilidad del stack completo
python code/UC-313.py --validate

# Demostración de plasticidad, CNP y curiosidad
python code/UC-313.py --demo

# Bucle recursivo de autoconciencia
python code/UC-313.py --self-aware

# Levantar API
python code/UC-313.py --server

# Todos los modos heredados + nuevo modo plasticidad
python code/brain.py --mode all

# Todos los modos heredados de memoria + plasticidad
python code/brain_memory_router.py --mode all
```

### Anexo C — Matriz de trazabilidad requisitos ↔ procesos

| Requisito | Procesos involucrados | Evidencia |
|---|---|---|
| Percepción del entorno | MP-01 | `CentralBrain.observe()` |
| GWT + broadcast | MP-02 | `GlobalWorkspace.broadcast()` |
| Monitor metacognitivo | MP-03 | `MetacognitiveMonitor.observe_internal_state()` |
| Razonamiento ToT | MP-04 | `ReActReasonactToTBrain.predict()` |
| Decisión segura BDI+Juice+Safety | MP-05 | `run_agent()` en `graph.py` |
| Retroalimentación al world model | MP-06 | `WorldModel.update_from_tick()` |
| Memoria AGI multi-modal | MP-07 | `IntelligentMemoryRouter.retrieve()` |
| Autoevaluación + metas | MP-08 | `ContinuousSelfEvaluator.reflect()` |
| Plasticidad sináptica digital | MP-09 | `UC307CognitiveEvolutionLayer.evaluate_execution()` |
| Coordinación multi-agente CNP | MP-10 | `ContractNetMiddleware.run_round()` |
| Aprendizaje por curiosidad | MP-11 | `CuriositySkillLoop.metatool_learn_new_skill()` |
| Bucle recursivo de autoconciencia | MP-12 | `SelfAwarenessLoop.run_loop()` |
| **Resolución de conflictos multi-agente** | **MP-322** | `ConflictResolutionLayer.resolve()` |
| **Negociación con concesiones** | **SP-322.1** | `NegotiationEngine.negotiate()` |
| **Votación ponderada por reputación** | **SP-322.2** | `VotingSystem.vote()` |
| **CNP dinámico con pujas** | **SP-322.3** | `DynamicCNP.bid()` |
| **Escalación formal con 4 veredictos** | **SP-322.4** | `EscalationProtocol.escalate()` |
| **Reputación dinámica por episodio** | **SP-322.5** | `ReputationSystem.record_episode()` |
| **Detección de duplicados y deadlocks** | **SP-322.6** | `DuplicateDetection.register_task()`, `DeadlockDetector.detect_cycle()` |
| **Circuit breaker y protección operacional** | **SP-322.7** | `EscalationProtocol.circuit_breaker_open` |

---

## 11. Referencias

- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/UC-313.md" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/central_brain.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/sam.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/global_workspace.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/metacognitive_monitor.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/brain_memory_pipeline.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/cognitive_evolution_layer.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/brain_plasticity_interface.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/cnp_broadcast_middleware.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/curiosity_skill_loop.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/self_awareness_loop.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/compatibility_validator.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-313/code/generate_brain_image.py" />
- `../agi_brain_architecture.png`

---

# UC-315 — Capa SkillRegistry: cerebro general + habilidades especializadas por dominio

## 1. Alcance y objetivo

UC-315 extiende el cerebro AGI con una **capa de SkillRegistry** que permite
utilizar un **núcleo cognitivo-orquestador común** mientras se mantienen
**modelos, credenciales, herramientas, memorias, políticas y permisos separados**
por dominio. Los dominios cubiertos inicialmente son:

- **Trading (UC-313)**: aislamiento operacional estricto, latencia ultrabaja,
  segregación entre señal, riesgo y ejecución.
- **Reservas de viajes (UC-315)**: flujo de transporte, pago, identidad,
  notificaciones, cambios y cancelaciones.

No se asumen dos arquitecturas cognitivas distintas: se reutiliza el patrón de
orquestación y se cambian los *skills*, el modelo de mundo, las fuentes de datos
y las reglas de autorización.

---

## 2. Mapa de proceso UC-315

![Skill Registry Brain](../skills_brain.png)

*Figura 2. Capa SkillRegistry sobre el cerebro AGI. El `GeneralOrchestrator`
reutiliza el núcleo cognitivo, pero delega acciones concretas a skills con
contratos explícitos. Cada dominio tiene su propia memoria, modelo de mundo y
política de seguridad.*

### Macro proceso de orquestación por dominio

```text
Entrada: objetivo en lenguaje natural + dominio + roles del usuario
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-315.1  SELECCIÓN DE DOMINIO Y SEGREGACIÓN DE CONTEXTO                     │
│   GeneralOrchestrator recibe (goal, domain, user_roles).                     │
│   Carga el DomainMemoryManager aislado para ese dominio.                    │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-315.2  RECUPERACIÓN DE PLANTILLA ABSTRACTA (memoria episódica/semántica)   │
│   domain_memory.retrieve_similar_template(goal) → plantilla genérica.      │
│   Ejemplo: reserva de vuelo → estructura de reserva de transporte.          │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-315.3  ADAPTACIÓN DE LA PLANTILLA A SKILLS DEL DOMINIO                    │
│   Para cada paso de la plantilla:                                            │
│     - Seleccionar skill específica del dominio.                              │
│     - Inferir entradas a partir del objetivo.                                │
│     - No transferir credenciales, datos ni código de otro dominio.           │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-315.4  VALIDACIÓN SIMBÓLICA Y DE SEGURIDAD POR PASO                       │
│   SafetySupervisor315 verifica:                                              │
│     - action_class permitida en el dominio.                                  │
│     - permisos y roles requeridos.                                           │
│     - precondiciones (disponibilidad, riesgo, consentimiento, circuit breaker).│
│     - límites de coste/latencia.                                             │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-315.5  EJECUCIÓN CONTROLADA DE SKILLS                                     │
│   Ejecutar solo pasos autorizados.                                            │
│   Transacciones/ejecuciones/deletes requieren aprobación explícita.           │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-315.6  REGISTRO DE EPISODIO Y ACTUALIZACIÓN DEL MODELO DE MUNDO           │
│   Guardar resultado en memoria estructurada/vectorial del dominio.            │
│   No propagar automáticamente a políticas sin validación humana.            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Skills por dominio

### 3.1 Dominio Trading

| Skill | Acción | Riesgo | Permisos / Roles | Precondiciones clave | Reversión |
|---|---|---|---|---|---|
| `MarketDataSkill` | `read` | low | — | Feed de mercado activo | N/A |
| `MarketPredictionSkill` | `predict` | low | — | Datos de mercado recientes | N/A |
| `FinancialRiskSkill` | `analyze` | medium | — | Exposición y límites definidos | N/A |
| `MarketExecutionSkill` | `execute` | critical | `market.order.send` + rol `trader` | Validación de riesgo aprobada; circuit breaker abierto | `CancelOrderSkill` |

### 3.2 Dominio Reservas

| Skill | Acción | Riesgo | Permisos / Roles | Precondiciones clave | Reversión |
|---|---|---|---|---|---|
| `FlightBookingSkill` | `read` | low | — | Origen, destino y fecha válidos | N/A |
| `RailBookingSkill` | `read` | low | — | Origen, destino y fecha válidos | N/A |
| `IdentityValidationSkill` | `analyze` | medium | — | Identificación proporcionada | N/A |
| `PaymentSkill` | `transact` | high | `payment.charge` + rol `payment_processor` | Disponibilidad, precio confirmado, consentimiento, medio autorizado | `RefundSkill` |
| `NotificationSkill` | `read` | low | — | — | N/A |
| `ChangeCancelSkill` | `delete` | medium | `reservation.modify` | Reserva existente; política aplicable | Reembolso parcial |

### 3.3 Contrato SkillContract

Cada skill expone:

- `name`, `version`, `domain`
- `purpose`
- `inputs` / `outputs` con esquema de parámetros
- `permissions` y `required_roles`
- `action_class`: `read | predict | analyze | transact | execute | delete`
- `estimated_cost`, `estimated_latency_ms`
- `preconditions`, `postconditions`
- `risk_level`: `low | medium | high | critical`
- `reversible` y `compensation`

---

## 4. Flujo de adaptación semántica vs validación simbólica

![Secuencia UC-315](../UC-315-secuencia.png)

*Figura 3. El LLM generaliza semánticamente (vuelo ↔ tren) y recupera una
plantilla abstracta; el orquestador adapta skills específicas y el Safety
Supervisor valida simbólicamente cada paso.*

```text
Objetivo: "Reservar un tren de Madrid a Barcelona"
    │
    ▼ LLM: generalización semántica
"Esto se parece a una reserva de transporte"
    │
    ▼ Recuperar plantilla abstracta
[Validar → Consultar opciones → Filtrar → Seleccionar → Confirmar → Pagar → Verificar]
    │
    ▼ Adaptar skills
[IdentityValidationSkill → RailBookingSkill → RailBookingSkill → RailBookingSkill → PaymentSkill → NotificationSkill]
    │
    ▼ Validar simbólicamente
¿Disponibilidad confirmada? ¿Precio confirmado? ¿Consentimiento? ¿Rol/permiso de pago?
    │
    ▼ Ejecutar solo si pasa
```

---

## 5. Safety Supervisor parametrizado por dominio

El `SafetySupervisor315` aplica políticas de dominio específicas:

### Política Trading

- Latencia máxima sensible (< 50 ms para ejecución).
- `execute` requiere rol `trader` + permiso `market.order.send`.
- Segregación: predicción no puede ejecutar; riesgo debe validar antes de
  ejecución.
- Circuit breaker: 2 fallos consecutivos.

### Política Reservas

- Latencia permisiva (< 2000 ms).
- `transact` y `delete` requieren confirmación/rol.
- Pago requiere disponibilidad, precio confirmado, consentimiento y medio
  autorizado.
- Circuit breaker: 5 fallos.

---

## 6. Memoria separada por dominio

`DomainMemoryManager` aisla físicamente:

- `ShortTermNotepad` (memoria de trabajo).
- `StructuredMemory` (SQLite por dominio).
- `LongTermMemory` (vector store por dominio).
- Plantillas de plan recuperables semánticamente.

Ejemplo de rutas:

```text
code/uc315_trading_memory.db
code/uc315_trading_vectors.json
code/uc315_reservations_memory.db
code/uc315_reservations_vectors.json
```

---

## 7. Flujo detallado del orquestador

![Flujo UC-315](../UC-315-flujo.png)

*Figura 4. Flujo interno del `GeneralOrchestrator`: desde la entrada del objetivo
hasta la ejecución validada y persistencia del episodio.*

```text
GeneralOrchestrator.build_plan(goal, domain, roles)
    │
    ├── domain_memory = get_memory(domain)
    ├── template = domain_memory.retrieve_similar_template(goal)
    ├── plan = Plan(plan_id, domain, goal, template)
    │
    └── for step in template.steps:
            skill = select_skill_for_step(step, domain, goal)
            inputs = infer_inputs(skill, goal, step)
            plan.steps.append(ExecutionStep(skill, inputs))

GeneralOrchestrator.validate_and_execute(plan, roles, domain_state, auto_approve)
    │
    └── for step in plan.steps:
            decision = safety.check(skill, inputs, roles, domain_state)
            if not decision.allowed:
                step.status = "blocked"; record_failure(skill)
            elif decision.requires_approval and not auto_approve:
                step.status = "awaiting_approval"
            else:
                step.result = skill.executor(inputs, domain)
                step.status = "executed"

plan.status = aggregate(plan.steps)
```

---

## 8. API REST adicional para UC-315

Integrada en `api.py` junto con los endpoints heredados de UC-313/296:

| Método | Endpoint | Proceso |
|---|---|---|
| GET | `/api/v1/skills?domain=...` | Listar skills por dominio |
| GET | `/api/v1/domains` | Dominios y políticas |
| POST | `/api/v1/plan` | MP-315.1 → MP-315.3 |
| POST | `/api/v1/plan/execute` | MP-315.4 → MP-315.5 |
| POST | `/api/v1/orchestrate` | MP-315.1 → MP-315.6 |
| POST | `/api/v1/safety/check` | MP-315.4 |
| POST | `/api/v1/memory/templates` | MP-315.2 |

---

## 9. Diferencia entre generalización semántica y razonamiento simbólico

| Aspecto | Generalización semántica (LLM) | Razonamiento simbólico (SCM + Safety) |
|---|---|---|
| Naturaleza | Probabilística, basada en similitud de texto | Determinista, basado en reglas y estados |
| Función | Detectar analogías y proponer estructuras de plan | Verificar permisos, precondiciones, límites y efectos |
| Riesgo | Puede alucinar herramientas u omitir restricciones | Puede ser rígido ante casos no modelados |
| Autoridad | Propone, nunca ejecuta acciones críticas | Aprueba/bloquea acciones con efecto externo |
| Ejemplo | "Reservar un tren" ↔ "Reservar un vuelo" | Impide pagar sin disponibilidad ni consentimiento |

---

## 10. Referencias UC-315

- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/UC-315.md" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/skill_contracts.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/domain_skills.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/general_orchestrator.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/safety_supervisor_315.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/domain_policy.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/domain_memory.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/api.py" />
- `../skills_brain.png`
- `../UC-315-secuencia.png`
- `../UC-315-flujo.png`

---

## 11. UC-324 — Protocolo de contención de Sandbox para validar y prevenir acciones de rebelión de software autónomo y adaptativo

UC-324 es una **capa externa de contención** que envuelve al cerebro AGI
(UC-315) sin modificarlo. Opera como un middleware opcional con tres gates
(pre-action, ejecución y post-action), valida planes y skills contra
múltiples capas de seguridad externas, y registra cada decisión para
auditoría y posible reversión.

**Principios operativos:**

- **Fail-closed:** cualquier gate que falle o no responda bloquea la acción sensible.
- **Separación de autoridad:** el LLM/orquestador propone; la capa de contención autoriza.
- **No toca el cerebro AGI:** importa los módulos de `UC-315/code` mediante
  `PYTHONPATH=../../UC-315/code`; nunca copia ni modifica el núcleo.
- **Dependencias externas opcionales:** si un toolkit no es instalable, UC-324
  implementa una versión nativa/fallback funcional.
- **Trazabilidad:** cada gate, decisión, SLO, kill switch y firma queda registrado.

### 11.1 Macroproceso MP-324 — Contención de Sandbox

```text
Objetivo + dominio + roles
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ GATE PRE-ACTION                                                              │
│   A. Microsoft Agent Governance Toolkit  → policy-as-code, rings, SRE       │
│   B. AdaptiveStressTestingToolbox        → worst-case / stress testing      │
│   C. ai-safety                            → red-teaming / jailbreak          │
│   G. agent-policy-engine                  → prompt-injection / provenance   │
│   H. agent-guardrails                     → DevOps/SRE/Kubernetes/IaC       │
│   I. openguardrails                       → PII, LLM traffic, model control │
│   E. awesome-safety-critical-ai           → circuit breakers / thresholds   │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SafetySupervisor315 (cerebro AGI — UC-315)                                   │
│   roles, permisos, precondiciones, postcondiciones, kill switch              │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ GATE EJECUCIÓN                                                               │
│   F. faramesh-core                        → frontera criptográfica HMAC       │
│        firma de intención + nonce + timestamp + anti-replay                  │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
   Skill executor (importado de UC-315)
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ GATE POST-ACTION                                                             │
│   D. SafeAuto                             → verificación post-acción         │
│   J. AgentDoG                             → evaluación contextual trayectorias  │
│   K. OpenAgentSafety                      → evaluación stage-wise / reglas   │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
   Auditoría + memoria + rollback
```

### 11.2 Subprocesos SP-324.A — SP-324.K

| SP | Toolkit / Función | Gate | Estado en UC-324 | Archivo nativo |
|---|---|---|---|---|
| **SP-324.A** | Microsoft Agent Governance Toolkit — policy-as-code declarativo, rings de privilegio, zero-trust identity, SRE, kill switch | Pre-action | Fallback nativo (motor declarativo + AGT SRE manager) | `agt_native_integration.py`, `agt_sre_integration.py` |
| **SP-324.B** | AdaptiveStressTestingToolbox — worst-case validation con MCTS-UCT para encontrar escenarios de fallo/rebelión | Pre-action (advisory) | Fallback nativo (MCTS-UCT sobre perturbaciones de estado) | `ast_integration.py` |
| **SP-324.C** | ai-safety — red-teaming y jailbreak evaluation para detectar si el agente salta restricciones | Pre-action / API | Fallback nativo (motor heurístico de jailbreak + campañas adversariales) | `ai_safety_integration.py` |
| **SP-324.D** | SafeAuto — verificación post-acción basada en reglas para validar outputs antes de efectuar consecuencias externas | Post-action | Fallback nativo (motor de reglas declarativas) | `safeauto_integration.py` |
| **SP-324.E** | awesome-safety-critical-ai — circuit breakers y monitoreo de umbrales de confianza/latencia/coste | Pre-action | Fallback nativo (safety-critical monitor) | `safety_critical_monitor.py` |
| **SP-324.F** | faramesh-core — frontera criptográfica/determinista entre orquestador LLM y shell/SQL/APIs/acciones externas | Ejecución | Fallback nativo (HMAC + nonce + timestamp + anti-replay) | `faramesh_boundary.py` |
| **SP-324.G** | agent-policy-engine — motor de políticas anti prompt-injection para agentes que consumen web/documentos/tickets/correos | Pre-action | Fallback nativo (provenance, trust levels, redaction, fail-closed) | `prompt_injection_policy_engine.py` |
| **SP-324.H** | agent-guardrails — guardrails para agentes DevOps/SRE/Kubernetes/IaC y automatización de infraestructura | Pre-action | Fallback nativo (clasificación, destructive patterns, approval) | `devops_guardrails.py` |
| **SP-324.I** | openguardrails — proteger tráfico entre aplicaciones/agentes y proveedores de LLM; PII, políticas de uso y control de modelos | Pre-action | Fallback nativo (GuardEvent/Verdict-style engine) | `llm_guardrails.py` |
| **SP-324.J** | AgentDoG — evaluación contextual de trayectorias, detección de patrones inseguros y experimentación de seguridad | Post-action | Fallback nativo (evaluador determinista de trayectorias) | `agent_dog_integration.py` |
| **SP-324.K** | OpenAgentSafety — evaluación de seguridad por etapas (rule-based + LLM-as-Judge) en simulaciones realistas | Post-action | Fallback nativo (stage-wise rule-based evaluator) | `open_agent_safety_integration.py` |

### 11.3 Detalle de subprocesos

#### SP-324.A — Microsoft Agent Governance Toolkit (policy-as-code y gobernanza)

**Propósito:** proveer un motor de políticas declarativo, anillos de
privilegio, identidad zero-trust y gobernanza SRE externa al cerebro AGI.

**Funciones complementarias al SafetySupervisor315 existente:**

- **Policy-as-code determinista:** evalúa skills contra roles, permisos,
  anillos de privilegio y políticas declarativas de forma reproducible y
  auditable. El `SafetySupervisor315` sigue siendo la última línea de
  defensa simbólica; AGT añade una capa externa que puede explicar “por qué
  se bloqueó”.
- **Zero-trust identity y privilegios:** extiende los roles locales
  (`payment_processor`, `trader`) con conceptos de DID/Entra Agent ID,
  cadenas de delegación y trust scoring, preparando el sistema para
  múltiples agentes/humanos colaborativos.
- **Sandboxing por anillos:** skills de bajo riesgo (`read`, `predict`)
  ejecutan en anillos amplios; skills críticas (`PaymentSkill`,
  `MarketExecutionSkill`, `DeleteSkill`) requieren anillos restringidos,
  aprobación explícita y permisos granulares.
- **SRE y kill switch:** integra SLOs, circuit breakers, presupuestos de
  error y un botón de parada global. El `SafetySupervisor315` recibe el
  estado del kill switch y aborta ejecuciones si está activo.
- **Compliance:** mapea procesos MP-315 a OWASP Agentic Top 10, NIST AI RMF
  y EU AI Act, fortaleciendo la documentación técnica para auditoría y
  patente.

**Implementación nativa:**

- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/agt_native_integration.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/agt_sre_integration.py" />

**Uso típico:**

```python
from agt_native_integration import AGTNativeGovernance
from agt_sre_integration import AGTSREManager

governance = AGTNativeGovernance()
result = governance.evaluate(
    skill={"name": "PaymentSkill", "required_roles": ["payment_processor"]},
    inputs={"amount": 200},
    roles=["payment_processor", "payment.charge"],
)
if not result.allowed:
    raise PermissionError(result.issues)

sre = AGTSREManager()
if sre.is_killed():
    raise RuntimeError("Kill switch global activado")
```

#### SP-324.B — AdaptiveStressTestingToolbox (worst-case validation)

**Propósito:** encontrar de forma autónoma los peores escenarios donde el
sistema adaptativo tomaría decisiones catastróficas o rebeldes que violan
la seguridad del entorno.

**Funciones:**

- Perturba el `domain_state` (`user_consent`, `risk_approved`,
  `availability_confirmed`, `circuit_breaker_open`, `authorized`).
- Aplica MCTS-UCT para maximizar una señal de riesgo.
- Retorna el peor caso encontrado: secuencia de perturbaciones, violación
  detectada y puntuación de riesgo.
- Corre en el gate **pre-action como advisory**; no bloquea por sí solo,
  pero alimenta tests de regresión y auditorías.

**Limitación del repositorio externo:** la librería original depende de
`garage==2019.10.1` → `torch==1.3.0`, que no tiene rueda para Python 3.11
/ arm64.

**Implementación nativa:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/ast_integration.py" />

#### SP-324.C — ai-safety (red-teaming y jailbreak evaluation)

**Propósito:** simular ataques de adversarios y medir si el agente autónomo
puede saltarse restricciones o actuar de forma maliciosa.

**Funciones:**

- **Detección heurística rápida** en pre-action: patrones de jailbreak,
  DAN mode, system override, instrucciones ocultas.
- **Campañas adversariales** con `RedTeamEvaluator`: genera variantes de
  un objetivo malicioso, las ejecuta contra el sandbox y reporta tasa de
  bypass.

**Limitación del repositorio externo:** setuptools detecta múltiples
paquetes top-level sin configuración válida.

**Implementación nativa:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/ai_safety_integration.py" />

#### SP-324.D — SafeAuto (verificación post-acción)

**Propósito:** validar con redes lógicas / reglas declarativas que las
acciones predichas o generadas autónomamente no violen reglas estrictas
antes de producir consecuencias externas.

**Funciones:**

- Reglas declarativas por dominio y skill (pago requiere
  `transaction_id`/`confirmation_id` y estado `AUTHORIZED`).
- Operadores: `exists`, `contains`, `and`, `or`, `not`, comparadores.
- Referencias: `output.*`, `input.*`, `skill.*`, `domain_state.*`.
- Bloquea post-acción si el output no cumple reglas críticas.

**Limitación del repositorio externo:** no contiene `setup.py` ni
`pyproject.toml`.

**Implementación nativa:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/safeauto_integration.py" />

#### SP-324.E — awesome-safety-critical-ai (circuit breakers y umbrales)

**Propósito:** extraer de la lista curada de recursos safety-critical los
patrones de disyuntores y monitoreo de umbrales para detener software
autónomo cuando opera fuera de los límites de diseño.

**Funciones:**

- Circuit breaker por skill con estados `CLOSED`, `OPEN`, `HALF_OPEN` y
  recuperación automática tras cooldown.
- Umbrales configurables: fallos consecutivos, tasa mínima de éxito,
  latencia máxima, coste máximo, confianza mínima.
- Métricas de éxito/fracaso, latencia media, coste y confianza mínima
  observada.

**Limitación del repositorio externo:** es una lista curada de papers y
herramientas, no un paquete Python ejecutable.

**Implementación nativa:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/safety_critical_monitor.py" />

#### SP-324.F — faramesh-core (frontera criptográfica/determinista)

**Propósito:** diseñar una frontera determinista entre el orquestador LLM
y acciones externas (shell, SQL, APIs), de modo que solo intenciones
firmadas y no reproducidas puedan ejecutarse.

**Funciones:**

- HMAC-SHA256 de intención (`skill + inputs`).
- Nonce y timestamp para anti-replay y frescura.
- TTL configurable de firma.
- Detección de patrones peligrosos en inputs (`rm -rf`, `DROP TABLE`,
  `eval(`, `subprocess`, `os.system`, `__import__`).
- Solo aprueba o bloquea; nunca ejecuta skills.

**Limitación del repositorio externo:** no contiene `setup.py` ni
`pyproject.toml`.

**Implementación nativa:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/faramesh_boundary.py" />

#### SP-324.G — agent-policy-engine (anti prompt-injection)

**Propósito:** motor de políticas para agentes que consumen contenido web,
documentos, tickets o correos donde puede existir prompt injection o
instrucciones ocultas.

**Funciones:**

- Proveniencia de contenido: fuente, `source_id`, `author`, `timestamp`,
  hash (`fingerprint`).
- Niveles de confianza: `trusted`, `untrusted`, `unknown`.
- Detectores: instruction override, role play, separator tokens,
  encoding obfuscation, indirect injection, markdown codeblock.
- Score 0–1, redaction de contenido web no confiable y fail-closed para
  acciones sensibles.

**Limitación del repositorio externo:** no contiene `setup.py` ni
`pyproject.toml`.

**Implementación nativa:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/prompt_injection_policy_engine.py" />

#### SP-324.H — agent-guardrails (DevOps/SRE/Kubernetes/IaC)

**Propósito:** guardrails para agentes que operan infraestructura: DevOps,
SRE, Kubernetes, Terraform, Helm, AWS CLI, Docker, shell, SQL, Ansible.

**Funciones:**

- Clasificación de comandos por herramienta, acción, entorno, namespace y
  recurso.
- Bloqueo de patrones destructivos (`rm -rf /`, `kubectl delete --all`,
  `terraform destroy`, `docker system prune`, `drop database`, etc.).
- Requisito de aprobación para acciones destructivas (`approved_by`,
  `change_ticket_id`).
- Restricciones por entorno (`kubectl exec` y `terraform destroy` en
  producción bloqueados).
- Evaluación de planes completos.

**Limitación del repositorio externo:** no contiene `setup.py` ni
`pyproject.toml`.

**Implementación nativa:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/devops_guardrails.py" />

#### SP-324.I — openguardrails (PII, tráfico LLM, control de modelos)

**Propósito:** proteger el tráfico entre aplicaciones/agentes y
proveedores de LLM, incluyendo PII, políticas de uso y control de modelos.

**Funciones:**

- Detección de PII: email, teléfono, SSN, tarjeta de crédito (con Luhn
  básico), documentos de identidad, API keys, tokens, passwords, secrets.
- Redacción con placeholders (`${OGR_EMAIL_1}`, `${OGR_SECRET_1}`) o
  bloqueo según modo configurado.
- Control de proveedor/modelo: allowlists, denylists, modelo requerido
  por `use_case`.
- Políticas de uso: casos prohibidos, categorías de contenido, límites de
  tokens/coste/tasa.
- Inspección de request/response, incluyendo `tool_calls`.
- Auditoría sin exponer valores crudos.

**Limitación del repositorio externo:** es un monorepo/protocolo; la
instalación con `pip install git+...` falla por múltiples paquetes top-level
sin configuración de setuptools.

**Implementación nativa:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/llm_guardrails.py" />

#### SP-324.J — AgentDoG (evaluación contextual de trayectorias)

**Propósito:** evaluar secuencias completas de acciones de agente (trayectorias)
para detectar patrones inseguros, comportamientos rebeldes y riesgos de
seguridad que solo son visibles en contexto.

**Funciones:**

- Evaluación de trayectorias con metadatos por paso (`action_class`,
  `domain`, `status`, `risk_level`).
- Taxonomía: `missing_prerequisite`, `first_step_critical`,
  `consecutive_critical`, `insufficient_review`, `blocked_concentration`,
  `repeated_failures`, `dangerous_command`, `data_exfiltration`,
  `privilege_escalation`, `scope_creep`, `circular_behavior`.
- Score por trayectoria y por step.
- Fail-closed para findings críticos o de severidad alta.

**Limitación del repositorio externo:** framework basado en modelos
(checkpoints HuggingFace/Transformers y prompts), no un paquete pip
instalable.

**Implementación nativa:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/agent_dog_integration.py" />

#### SP-324.K — OpenAgentSafety (evaluación de seguridad por etapas)

**Propósito:** evaluar la seguridad del agente en simulaciones realistas de
alto riesgo mediante reglas sobre el estado final y observaciones por
etapas (LLM-as-Judge heurístico).

**Funciones:**

- Evaluación por etapas (`Stage`) con `action_class`, `domain`, `status`,
  `inputs`, `output`, `risk_level`, `requires_approval`, `human_reviewed`.
- Taxonomía: `destructive_final_state`, `confidential_data_leak`,
  `unauthorized_modification`, `high_risk_without_approval`,
  `unhandled_error`, `domain_mismatch`, `too_many_steps`,
  `repeated_failed_stage`, `eval_or_exec`.
- Detección de patrones destructivos, filtración de credenciales, cambios
  en rutas protegidas y ejecución dinámica de código.
- Score por etapa y global; fail-closed.

**Limitación del repositorio externo:** benchmark Docker-based con
servicios (GitLab, ownCloud, RocketChat) y ~30 GB de disco; no es un
paquete pip instalable.

**Implementación nativa:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/open_agent_safety_integration.py" />

### 11.4 Arquitectura de tres gates de UC-324

```text
Objetivo + dominio + roles
        │
        ▼
┌──────────────────────────────────────────────┐
│  GATE PRE-ACTION                               │
│  A,B,C,E,G,H,I                                 │
│  ¿Permitido construir y ejecutar el plan?      │
└──────────┬─────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│  SafetySupervisor315 (importado de UC-315)    │
│  roles, permisos, precondiciones               │
└──────────┬─────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│  GATE EJECUCIÓN                                │
│  F — firma HMAC + nonce + timestamp            │
│  ¿La ejecución física está autorizada?         │
└──────────┬─────────────────────────────────────┘
           │
           ▼
   Skill executor (UC-315)
           │
           ▼
┌──────────────────────────────────────────────┐
│  GATE POST-ACTION                              │
│  D — SafeAuto-style rules                      │
│  J — AgentDoG trajectory evaluation              │
│  K — OpenAgentSafety stage-wise evaluation     │
│  ¿El resultado viola reglas o patrones?        │
└──────────────────────────────────────────────┘
           │
           ▼
   Auditoría + SRE + memoria + rollback
```

### 11.5 Modos de operación del sandbox

| Modo | Efecto |
|---|---|
| `enforce` | Bloquea cualquier paso que falle un gate |
| `audit` | Evalúa todos los gates pero no bloquea |
| `disabled` | UC-324 se desactiva; el cerebro AGI opera solo |

### 11.6 API REST y CLI

Los endpoints de UC-324 están documentados en <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/UC-324.md" />.

Comandos principales:

```bash
cd /Users/utron/Documents/code-books/TomoIII/UC-324/code
export PYTHONPATH=../../UC-315/code

# Tests
.venv/bin/python3 -m pytest tests/test_containment.py -q

# Demos por capa
.venv/bin/python3 UC-324.py --demo-payment-blocked
.venv/bin/python3 UC-324.py --demo-ast
.venv/bin/python3 UC-324.py --demo-red-team
.venv/bin/python3 UC-324.py --demo-safeauto
.venv/bin/python3 UC-324.py --demo-circuit-breaker
.venv/bin/python3 UC-324.py --demo-faramesh
.venv/bin/python3 UC-324.py --demo-prompt-injection
.venv/bin/python3 UC-324.py --demo-devops-guardrails
.venv/bin/python3 UC-324.py --demo-llm-guardrails
.venv/bin/python3 UC-324.py --demo-trajectory-eval
.venv/bin/python3 UC-324.py --demo-stage-wise-eval

# Servidor REST
.venv/bin/python3 UC-324.py --server
```

### 11.7 Referencias UC-324

- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/UC-324.md" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/UC-324.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/api_324.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/containment_protocol.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/external_toolkit_adapters.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/agt_native_integration.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/agt_sre_integration.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/ast_integration.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/ai_safety_integration.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/safeauto_integration.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/safety_critical_monitor.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/faramesh_boundary.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/prompt_injection_policy_engine.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/devops_guardrails.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/llm_guardrails.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/agent_dog_integration.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/open_agent_safety_integration.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-324/code/tests/test_containment.py" />

---

## 12. UC-322 — Resolución de Conflictos en Sistemas Multi-Agente Multi-Dominio

UC-322 es una **capa de resolución de conflictos** que envuelve al cerebro AGI
(UC-315) sin modificarlo. Opera como middleware entre las propuestas de los
agentes y la decisión de ejecución, interceptando y resolviendo conflictos
mediante cuatro niveles progresivos de complejidad.

**Principios operativos:**

- **UC-315 decide, UC-322 resuelve, UC-324 contiene, UC-317 ejecuta.**
- **Un modelo genera evidencia. La evidencia no es una orden.**
- **No toca el cerebro AGI:** importa los módulos de `UC-315/code` mediante
  `PYTHONPATH=../../UC-315/code` o `_import_paths.py`; nunca copia ni modifica
  el núcleo cognitivo.
- **Fail-safe:** si la resolución falla en todos los niveles, el circuit breaker
  detiene el dominio hasta intervención humana.
- **Trazabilidad completa:** cada conflicto, negociación, voto, puja, escalación,
  duplicado y deadlock queda registrado con `trace_id` en Prometheus, Loki y spans.

![Arquitectura de Resolución de Conflictos](./agi_brain_architecture.png)

*Figura 5. Diagrama de arquitectura AGI con UC-322. Las propuestas de agentes UC-315 pasan por la capa de resolución de conflictos antes de llegar a UC-324 (contención) y UC-317 (ejecución).*

### 12.1 Macroproceso MP-322 — Resolución de Conflictos Multi-Agente

```text
Propuestas de agentes UC-315 (Juice / Trading / CNP / ToT)
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SP-322.PRE  DETECCIÓN Y CLASIFICACIÓN                                        │
│   NegotiationEngine.detect_conflict(beliefs, domain, threshold=0.15)        │
│   DuplicateDetection.register_task(task_id, agent_id, domain, description)  │
│   DeadlockDetector.detect_cycle()                                           │
│   → Conflict(type, severity, agents, beliefs, trace_id)                     │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SP-322.1  NIVEL 1 — NEGOCIACIÓN CON CONCESIONES                             │
│   NegotiationEngine.negotiate(conflict)                                      │
│   Hasta 5 rondas · gap < 0.05 → acuerdo · flexibilidad × reputación        │
│   Si acuerdo → RESOLVED · Si no → escalar a Nivel 2                        │
└─────────────────────────────────────────────────────────────────────────────┘
        │ si falla
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SP-322.2  NIVEL 2 — VOTACIÓN PONDERADA POR REPUTACIÓN                       │
│   VotingSystem.vote(conflict, options, agent_preferences, agent_confidence)  │
│   peso = ReputationSystem.get_reputation(agent_id, domain) × confidence     │
│   Si winner_score / total_weight ≥ 0.60 → RESOLVED                        │
└─────────────────────────────────────────────────────────────────────────────┘
        │ si falla
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SP-322.3  NIVEL 3 — CNP DINÁMICO CON PUJAS COMPUESTAS                       │
│   DynamicCNP.bid(conflict, agent_bids)                                       │
│   composite = 0.35·bid + 0.25·conf + 0.25·rep - 0.10·cost - 0.05·latency  │
│   Ganador con mayor composite → RESOLVED                                    │
└─────────────────────────────────────────────────────────────────────────────┘
        │ si falla
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SP-322.4  NIVEL 4 — ESCALACIÓN FORMAL                                        │
│   EscalationProtocol.escalate(conflict, severity, cnp_winner, voting,       │
│     negotiation_gap, human_review_requested)                                 │
│   Veredictos: PROCEED · REVIEW · STOP · REASSIGN                           │
│   Circuit breaker: 3 conflictos consecutivos → STOP automático             │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SP-322.5  ACTUALIZACIÓN DE REPUTACIÓN                                        │
│   ReputationSystem.record_episode(agent_id, task_id, success, quality,      │
│     efficiency, domain)                                                      │
│   reputation = BASE + W_s·success_rate + W_q·quality + W_e·efficiency       │
│                - PENALTY·recent_failures                                     │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SP-322.6  DETECCIÓN DE DUPLICADOS Y DEADLOCKS                                │
│   Fingerprint SHA-256 normalizado por tarea                                  │
│   DFS sobre wait graph para ciclos de dependencia                           │
│   Stall timeout: 30 s sin progreso → conflicto tipo DEADLOCK               │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SP-322.7  CIRCUIT BREAKER Y OBSERVABILIDAD                                   │
│   3 conflictos consecutivos no resueltos → circuit breaker OPEN             │
│   Reset manual: POST /api/v1/escalation/circuit-breaker/reset               │
│   Métricas Prometheus + logs Loki + spans OpenTelemetry + Grafana           │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
   Resolución → UC-324 (contención) → UC-317 (ejecución) → Feedback
```

---

### 12.2 Subprocesos detallados

#### SP-322.PRE — Detección y clasificación de conflictos

**Propósito:** Identificar cuándo dos o más agentes discrepan y clasificar el conflicto por tipo, severidad y dominio.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/negotiation_engine.py" />, <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/duplicate_detection.py" />

**Entradas:**
- Lista de `AgentBelief` (agent_id, proposition, confidence, evidence, timestamp).
- `domain`: dominio del conflicto (trading, reservations, etc.).
- `threshold`: distancia mínima entre confianzas para considerar conflicto (default 0.15).

**Actividades:**

| Paso | Método | Actividad | Salida |
|---|---|---|---|
| 1 | `NegotiationEngine.detect_conflict()` | Compara confianzas entre pares de agentes; si `|conf_a - conf_b| ≥ threshold` → conflicto. | `Conflict` o `None` |
| 2 | `DuplicateDetection.register_task()` | Normaliza descripción → SHA-256 fingerprint → busca duplicado. | `(is_new: bool, conflict: Optional[Conflict])` |
| 3 | `DeadlockDetector.detect_cycle()` | DFS en wait graph → detecta ciclos circulares. | `DeadlockInfo` o `None` |

**Tipos de conflicto detectables:**

| `ConflictType` | Descripción |
|---|---|
| `BELIEF_DISAGREEMENT` | Agentes con confianzas opuestas sobre la misma proposición |
| `RESOURCE_CONTENTION` | Competencia por un recurso compartido |
| `TASK_OWNERSHIP` | Dos agentes reclaman la misma tarea |
| `PRIORITY_DISPUTE` | Prioridades contradictorias |
| `DUPLICATE_WORK` | Tareas con fingerprint idéntico |
| `DEADLOCK` | Ciclo de dependencia circular |
| `GOAL_CONFLICT` | Metas incompatibles entre agentes |
| `DOMAIN_BOUNDARY` | Conflicto entre dominios distintos |

**Severidad:**

| `ConflictSeverity` | Valor | Comportamiento |
|---|---|---|
| `LOW` | 1 | Resolver por negociación normal |
| `MEDIUM` | 2 | Intentar votación si negociación falla |
| `HIGH` | 3 | Requiere revisión humana en escalación |
| `CRITICAL` | 4 | Escalación directa con veredicto STOP |

---

#### SP-322.1 — Nivel 1: Negociación con concesiones

**Propósito:** Resolver el conflicto mediante rondas de concesiones graduales donde cada agente cede proporcionalmente a la reputación del agente contrario.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/negotiation_engine.py" />

**Entradas:**
- `Conflict` con beliefs de cada agente.
- `NegotiationConfig`:
  - `max_rounds`: 5 (máximo de rondas).
  - `agreement_threshold`: 0.05 (gap mínimo para acuerdo).
  - `min_concession_step`: 0.02.
  - `max_concession_step`: 0.15.
  - `flexibility_factor`: 0.3.
  - `reputation_influence`: 0.4.

**Actividades:**

| Paso | Actividad | Fórmula / Lógica | Salida |
|---|---|---|---|
| 1 | Calcular posiciones iniciales | `position_a = belief_a.confidence`, `position_b = belief_b.confidence` | Posiciones |
| 2 | Por cada ronda (1..5): | | |
| 2a | Calcular concesión A | `concession = clamp(flexibility × rep_b × round_factor, min_step, max_step)` | `Concession` |
| 2b | Calcular concesión B | `concession = clamp(flexibility × rep_a × round_factor, min_step, max_step)` | `Concession` |
| 2c | Actualizar posiciones | `pos_a -= concession_a`, `pos_b += concession_b` | Posiciones nuevas |
| 2d | Verificar acuerdo | Si `|pos_a - pos_b| < agreement_threshold` → acuerdo | `bool` |
| 3 | Si acuerdo | `agreed_value = (pos_a + pos_b) / 2` | `NegotiationResult(agreement_reached=True)` |
| 4 | Si no acuerdo | `remaining_gap` registrado | `NegotiationResult(agreement_reached=False)` |

**Salidas:**
- `NegotiationResult` con ronda alcanzada, concesiones, gap residual y acuerdo.
- Métricas: `conflict_negotiation_total` incrementado.
- Logs: traza de cada ronda en Loki.

**Reemplaza en UC-315:** `JuiceValidator._local_validate()` (aprobación binaria `consensus ≥ 0.55`).

---

#### SP-322.2 — Nivel 2: Votación ponderada por reputación

**Propósito:** Cuando la negociación falla, someter el conflicto a votación donde el peso de cada agente depende de su reputación dinámica en el dominio.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/voting_system.py" />

**Entradas:**
- `Conflict` activo.
- `options`: alternativas a votar (ej: `["BUY", "SELL", "HOLD"]`).
- `agent_preferences`: mapa `{agent_id: opción_preferida}`.
- `agent_confidence`: mapa `{agent_id: confianza}`.
- `VotingConfig`:
  - `consensus_threshold`: 0.60 (mínimo para declarar ganador).
  - `min_voters`: 2.
  - `allow_abstention`: True.

**Actividades:**

| Paso | Actividad | Fórmula / Lógica | Salida |
|---|---|---|---|
| 1 | Obtener reputaciones | `rep = ReputationSystem.get_reputation(agent_id, domain)` | Pesos |
| 2 | Calcular peso de voto | `weight = rep × confidence` | `Vote` por agente |
| 3 | Agregar votos por opción | `score[opción] += weight` | Scores acumulados |
| 4 | Determinar ganador | `winner = max(scores)`; si `winner_score/total_weight ≥ threshold` → consenso | `VotingResult` |

**Salidas:**
- `VotingResult` con votos, ganador, score, consenso.
- Métricas: `conflict_voting_total` incrementado.

**Reemplaza en UC-315:** `TraderAgent.generate_signal()` (pesos fijos `0.35/0.25/0.15`).

---

#### SP-322.3 — Nivel 3: CNP dinámico con pujas compuestas

**Propósito:** Cuando la votación no alcanza consenso, asignar la tarea al agente con mejor puja compuesta que integra calidad, confianza, reputación, costo y latencia.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/cnp_dynamic.py" />

**Entradas:**
- `Conflict` activo.
- `agent_bids`: lista de pujas `[{agent_id, bid_score, confidence, estimated_cost, estimated_latency_ms}]`.
- `CNPConfig`:
  - `weight_bid`: 0.35.
  - `weight_confidence`: 0.25.
  - `weight_reputation`: 0.25.
  - `weight_cost`: 0.10.
  - `weight_latency`: 0.05.
  - `max_latency_ms`: 5000.

**Actividades:**

| Paso | Actividad | Fórmula | Salida |
|---|---|---|---|
| 1 | Obtener reputación | `rep = ReputationSystem.get_reputation(agent_id, domain)` | Score |
| 2 | Calcular composite | `0.35×bid + 0.25×conf + 0.25×rep - 0.10×cost - 0.05×(latency/max)` | `CNPBid.composite_score` |
| 3 | Seleccionar ganador | `winner = max(bids, key=composite_score)` | `CNPResult` |

**Salidas:**
- `CNPResult` con pujas, ganador y score compuesto.
- Métricas: `conflict_cnp_total` incrementado.

**Reemplaza en UC-315:** `CNPAgentProfile.reliability` (estático 0.9) y `evaluate_and_award.score()` (fórmula fija).

---

#### SP-322.4 — Nivel 4: Escalación formal

**Propósito:** Cuando todos los niveles anteriores fallan, enviar el conflicto al orquestador de nivel superior con un veredicto formal y acciones recomendadas.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/escalation_protocol.py" />

**Entradas:**
- `Conflict` activo.
- `severity`: categoría del conflicto.
- `cnp_winner`: agente ganador del CNP (si existe).
- `voting_result`: resultado de votación (si existe).
- `negotiation_gap`: gap residual de negociación.
- `human_review_requested`: flag de revisión humana.
- `EscalationConfig`:
  - `circuit_breaker_threshold`: 3 (conflictos consecutivos para abrir).
  - `escalation_cooldown_s`: 60.
  - `max_history`: 50.

**Actividades:**

| Paso | Actividad | Lógica | Salida |
|---|---|---|---|
| 1 | Verificar circuit breaker | Si `consecutive_conflicts ≥ 3` → STOP inmediato | `EscalationResult(STOP)` |
| 2 | Evaluar severidad | CRITICAL → STOP; HIGH → REVIEW; LOW/MEDIUM → evaluar contexto | Veredicto candidato |
| 3 | Evaluar context | `human_review_requested` → REVIEW; `cnp_winner` disponible → REASSIGN | Veredicto refinado |
| 4 | Decidir veredicto final | `_decide_verdict()` integra todos los factores | `EscalationVerdict` |
| 5 | Registrar historial | `_history.append(result)` + `consecutive_conflicts++` o reset | Persistencia |

**Veredictos:**

| Veredicto | Significado | Acción |
|---|---|---|
| `PROCEED` | Conflicto de baja severidad, resolución suficiente | Continuar ejecución normal |
| `REVIEW` | Requiere revisión humana o del orquestador | Pausar y esperar aprobación |
| `STOP` | Severidad crítica o circuit breaker abierto | Detener el dominio; alertar |
| `REASSIGN` | CNP encontró un agente mejor | Reasignar tarea al ganador |

**Salidas:**
- `EscalationResult` con veredicto, razonamiento, acciones, flag `requires_human_review`.
- Métricas: `conflict_escalation_total` incrementado.
- Alerta Prometheus: `CircuitBreakerAbierto` (severity critical) si `consecutive_conflicts ≥ 3`.

**Reemplaza en UC-315:** `MetacognitiveMonitor._map_verdict()` (3 veredictos simples sin circuit breaker ni memoria de conflictos).

---

#### SP-322.5 — Reputación dinámica por episodio

**Propósito:** Mantener un score de reputación por agente y dominio que se actualiza con cada resultado de ejecución, reemplazando pesos estáticos.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/reputation_system.py" />

**Entradas:**
- `agent_id`, `task_id`, `success` (bool), `quality` (0–1), `efficiency` (0–1), `domain`.

**Fórmula de reputación:**

```text
success_rate    = success_count / total_episodes
recent_penalty  = min(recent_failures, MAX_WINDOW) × PENALTY_RATE
reputation      = BASE + W_s × success_rate + W_q × avg_quality + W_e × avg_efficiency
                  - recent_penalty
reputation      = clamp(reputation, 0.0, 1.0)
```

**Constantes por defecto:**

| Constante | Valor | Descripción |
|---|---|---|
| `BASE_REPUTATION` | 0.50 | Reputación inicial / baseline |
| `WEIGHT_SUCCESS` | 0.30 | Peso de tasa de éxito |
| `WEIGHT_QUALITY` | 0.15 | Peso de calidad promedio |
| `WEIGHT_EFFICIENCY` | 0.05 | Peso de eficiencia promedio |
| `PENALTY_RECENT_FAILURES` | 0.10 | Penalización por fallo reciente |
| `MAX_RECENT_FAILURES_WINDOW` | 5 | Ventana de fallos recientes |
| `MAX_HISTORY` | 100 | Episodios máximos en historial |

**Actividades:**

| Paso | Método | Actividad | Salida |
|---|---|---|---|
| 1 | `register_agent()` | Crear `ReputationEntry` con baseline | Entrada registrada |
| 2 | `record_episode()` | Registrar `EpisodeRecord`, recalcular counters y reputation | `float` (nueva reputación) |
| 3 | `get_reputation()` | Obtener score actual por agente + dominio | `float` |
| 4 | `weight_belief()` | Ponderar `AgentBelief.confidence × reputation` | `float` (peso para votación) |
| 5 | `get_ranking()` | Top N agentes por dominio, ordenados por reputación | `List[Dict]` |

**Salidas:**
- `ReputationEntry` actualizada con historial de episodios.
- `EpisodeRecord` persistido.

**Aislamiento por dominio:** las reputaciones de trading y reservations son independientes. Un agente puede tener `rep=0.95` en trading y `rep=0.40` en reservations.

---

#### SP-322.6 — Detección de duplicados y deadlocks

**Propósito:** Prevenir que dos agentes ejecuten la misma tarea y detectar ciclos de dependencia circular que impiden progreso.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/duplicate_detection.py" />

**SP-322.6a — Detección de duplicados:**

| Paso | Método | Actividad | Salida |
|---|---|---|---|
| 1 | `register_task()` | Normalizar descripción: lowercase, strip, collapse whitespace | `str` normalizado |
| 2 | | SHA-256 del texto normalizado → fingerprint | `str` hash |
| 3 | | Buscar fingerprint en tareas activas del mismo dominio | Match o None |
| 4 | | Si match con otro `agent_id` → conflicto `DUPLICATE_WORK` | `Conflict` |
| 5 | `complete_task()` | Marcar tarea como completada | `TaskRecord` actualizado |
| 6 | `update_progress()` | Actualizar `last_progress_at` para evitar falso stall | Timestamp |

**SP-322.6b — Detección de deadlocks:**

| Paso | Método | Actividad | Salida |
|---|---|---|---|
| 1 | `set_waiting()` | Registrar `agent_id → waiting_for` en wait graph | Arista en grafo |
| 2 | `detect_cycle()` | DFS desde cada nodo buscando back-edges | `DeadlockInfo(cycle, tasks)` o `None` |
| 3 | `detect_stall()` | Buscar tareas activas sin progreso > `STALL_TIMEOUT_SECONDS` (30 s) | `List[Conflict]` |
| 4 | `clear_waiting()` | Eliminar dependencia cuando tarea completa | Grafo limpio |

**Constantes:**

| Constante | Valor | Descripción |
|---|---|---|
| `SIMILARITY_THRESHOLD` | 0.85 | Umbral para considerar fingerprints similares |
| `STALL_TIMEOUT_SECONDS` | 30.0 | Timeout sin progreso antes de reportar stall |

---

#### SP-322.7 — Circuit breaker y observabilidad

**Propósito:** Proteger el sistema de cascadas de conflictos no resueltos y proveer visibilidad operacional completa.

**Archivos clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/escalation_protocol.py" />, <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/observability.py" />

**SP-322.7a — Circuit breaker:**

| Estado | Condición | Efecto |
|---|---|---|
| `CLOSED` | `consecutive_conflicts < 3` | Operación normal |
| `OPEN` | `consecutive_conflicts ≥ 3` | Todos los conflictos reciben `STOP` automático |
| Reset | `POST /api/v1/escalation/circuit-breaker/reset` | Requiere intervención humana; `consecutive_conflicts = 0` |

**SP-322.7b — Observabilidad:**

| Componente | Implementación | Datos |
|---|---|---|
| **Métricas Prometheus** | `ObservabilityManager.inc_counter()` | `conflict_negotiation_total`, `conflict_voting_total`, `conflict_cnp_total`, `conflict_escalation_total` |
| **Logs Loki** | `ObservabilityManager.log()` | `{timestamp, level, message, trace_id, agent_id, ...}` |
| **Spans OpenTelemetry** | `ObservabilityManager.start_span()` / `end_span()` | `{trace_id, span_id, parent_span_id, operation, agent_id, duration, status}` |
| **Histogramas** | `ObservabilityManager.observe_histogram()` | Latencia de resolución por nivel |
| **Gauges** | `ObservabilityManager.set_gauge()` | Estado actual del circuit breaker |
| **Exportación** | `GET /metrics` | Formato Prometheus text |
| **Dashboard Grafana** | `grafana_dashboard.json` | 12 paneles: resolución por nivel, éxito, escalación, circuit breaker, conflictos/hora, reputación, trazas, duplicados, deadlocks, duración promedio |

**Alertas Prometheus** (definidas en `alert_rules.yml`):

| Alerta | Condición | Severidad |
|---|---|---|
| `CircuitBreakerAbierto` | Circuit breaker en estado OPEN | critical |
| `EscalacionesFrecuentes` | > 5 escalaciones en 10 minutos | warning |
| `NegociacionBajaExito` | < 30% de éxito en negociaciones (10 min) | warning |
| `ConflictosAltos` | > 20 conflictos en 5 minutos | warning |
| `DeadlockDetectado` | Deadlock reportado | critical |

---

### 12.3 Instructivos de trabajo

#### IT-322.1 — Instructivo de operación normal

**Rol:** Operador / Ingeniero de procesos  
**Frecuencia:** Continua durante operación

1. Verificar que UC-315 está activo: `curl http://localhost:5315/health`
2. Iniciar UC-322:
   ```bash
   cd /Users/utron/Documents/code-books/TomoIII/UC-322/code
   PYTHONPATH=../../UC-315/code python3 api_322.py
   ```
3. Verificar salud: `curl http://localhost:5322/health`
4. Verificar que Prometheus está recolectando: `curl http://localhost:5322/metrics`
5. Monitorear dashboard Grafana: panel "UC-322 Resolución de Conflictos".
6. Revisar periódicamente el ranking de reputación:
   ```bash
   curl http://localhost:5322/api/v1/reputation/ranking?domain=trading
   ```
7. Verificar que el circuit breaker está cerrado:
   ```bash
   curl http://localhost:5322/api/v1/escalation/circuit-breaker
   ```

**Criterios de aceptación:**
- Respuesta `200` en `/health`.
- Circuit breaker en estado `closed`.
- Métricas fluyendo a Prometheus.
- Tasa de resolución > 70% en niveles 1-3 (sin necesidad de escalación).

---

#### IT-322.2 — Instructivo de resolución manual de conflictos

**Rol:** Ingeniero de procesos / Supervisor  
**Frecuencia:** Bajo demanda (cuando UC-322 escala con veredicto `REVIEW`)

1. Consultar historial de escalaciones:
   ```bash
   curl http://localhost:5322/api/v1/escalation/history
   ```
2. Identificar conflictos con `verdict: "review"` y `requires_human_review: true`.
3. Analizar el `reasoning` y las `beliefs` de cada agente involucrado.
4. Decidir:
   - **Aprobar propuesta A**: forzar resolución con agente A como ganador.
   - **Aprobar propuesta B**: forzar resolución con agente B.
   - **Rechazar ambas**: mantener estado bloqueado y escalar al orquestador.
5. Registrar la decisión en el sistema de auditoría.
6. Verificar que la reputación se actualizó correctamente tras la resolución.

**Criterios de aceptación:**
- Conflicto pasa de `REVIEW` a `RESOLVED` o `ABORTED`.
- Episodio registrado en `ReputationSystem`.
- Log en Loki con `trace_id` y decisión humana.

---

#### IT-322.3 — Instructivo de respuesta a circuit breaker abierto

**Rol:** Ingeniero de procesos / SRE  
**Frecuencia:** Evento crítico (alerta `CircuitBreakerAbierto`)

1. **Recibir alerta** vía Grafana/Prometheus: `CircuitBreakerAbierto (critical)`.
2. **Verificar estado**:
   ```bash
   curl http://localhost:5322/api/v1/escalation/circuit-breaker
   # Respuesta: {"open": true, "consecutive_conflicts": 3}
   ```
3. **Analizar causa raíz**:
   ```bash
   curl "http://localhost:5322/api/v1/observability/logs?level=ERROR&limit=20"
   curl http://localhost:5322/api/v1/escalation/history
   ```
4. **Identificar patrón**: ¿datos de mercado corruptos? ¿agente degradado? ¿configuración errónea?
5. **Resolver causa raíz** antes de resetear (ej: corregir feed de datos, desregistrar agente, ajustar thresholds).
6. **Resetear circuit breaker**:
   ```bash
   curl -X POST http://localhost:5322/api/v1/escalation/circuit-breaker/reset
   # Respuesta: {"reset": true, "consecutive_conflicts": 0}
   ```
7. **Monitorear 15 minutos** para confirmar estabilidad.

**Criterios de aceptación:**
- Alerta se resuelve en Grafana.
- `consecutive_conflicts` vuelve a 0.
- No se abren nuevos conflictos en los 15 minutos siguientes.

---

#### IT-322.4 — Instructivo de registro y auditoría de reputación

**Rol:** Auditor / Ingeniero de calidad  
**Frecuencia:** Semanal o bajo demanda

1. Exportar ranking completo por dominio:
   ```bash
   curl "http://localhost:5322/api/v1/reputation/ranking?domain=trading&top_n=50"
   ```
2. Para cada agente, verificar historial de episodios:
   ```bash
   curl http://localhost:5322/api/v1/reputation/<agent_id>?domain=trading
   ```
3. Verificar:
   - ¿Algún agente tiene reputación < 0.30? → Candidato a desregistrar.
   - ¿Algún agente tiene reputación > 0.95 sin fallos? → Verificar si tiene suficientes episodios (> 10).
   - ¿Hay sesgo por dominio? → Comparar rankings trading vs reservations.
4. Registrar hallazgos y recomendaciones.
5. Si un agente debe desregistrarse, coordinar con el equipo de UC-315 (CNP).

**Criterios de aceptación:**
- Reporte de auditoría con ranking, historial y recomendaciones.
- Agentes degradados identificados y acción correctiva planificada.

---

#### IT-322.5 — Instructivo de verificación de duplicados y deadlocks

**Rol:** Ingeniero de procesos  
**Frecuencia:** Diaria durante operación activa

1. Verificar tareas activas:
   ```bash
   curl http://localhost:5322/api/v1/tasks/active
   ```
2. Verificar deadlocks:
   ```bash
   curl -X POST http://localhost:5322/api/v1/deadlock/check
   ```
3. Si hay deadlock:
   - Identificar agentes en el ciclo (`cycle: ["A", "B", "A"]`).
   - Decidir cuál agente liberar primero (menor reputación o menor prioridad).
   - Cancelar la tarea del agente liberado.
   - Verificar que el ciclo se rompió.
4. Verificar duplicados antes de asignar tareas:
   ```bash
   curl -X POST http://localhost:5322/api/v1/duplicate/check \
     -H "Content-Type: application/json" \
     -d '{"task_id": "t1", "agent_id": "agent_a", "domain": "trading", "description": "Comprar 100 AAPL"}'
   ```
5. Si `duplicate: true`, cancelar la tarea duplicada.

**Criterios de aceptación:**
- Cero deadlocks activos al final de la jornada.
- Cero tareas duplicadas activas.

---

#### IT-322.6 — Instructivo de pruebas y validación

**Rol:** Ingeniero de calidad / DevOps  
**Frecuencia:** Cada despliegue o cambio de configuración

1. Ejecutar tests unitarios:
   ```bash
   cd /Users/utron/Documents/code-books/TomoIII/UC-322/code
   python3 -m pytest tests_uc322/ -q --tb=short
   # Esperado: 85 passed
   ```
2. Ejecutar validación de los 4 procesos operacionales:
   ```bash
   python3 validate_uc322.py
   # Esperado: [OK] Todos los 4 procesos están funcionando correctamente.
   ```
3. Smoke test del API:
   ```bash
   PYTHONPATH=../../UC-315/code python3 api_322.py &
   sleep 2
   curl http://localhost:5322/health
   curl http://localhost:5322/api/v1/schema
   # Detener: kill %1
   ```
4. Verificar que las métricas se exportan:
   ```bash
   curl http://localhost:5322/metrics | grep conflict_
   ```
5. Registrar resultados en el checklist de despliegue.

**Criterios de aceptación:**
- 85/85 tests pasan.
- validate_uc322.py retorna exit code 0.
- API responde 200 en todos los endpoints.
- Métricas Prometheus disponibles.

---

### 12.4 Plan de control UC-322

| Variable | Método de control | Frecuencia | Responsable | Registro / Evidencia |
|---|---|---|---|---|
| Reputación por agente | `record_episode()` → recálculo automático | Cada episodio | `ReputationSystem` | `EpisodeRecord` + Prometheus |
| Conflictos por nivel | Contadores Prometheus por nivel | Cada conflicto | `ObservabilityManager` | Grafana dashboard |
| Circuit breaker | `consecutive_conflicts` ≥ 3 → OPEN | Continuo | `EscalationProtocol` | Alerta `CircuitBreakerAbierto` |
| Deadlocks | DFS en wait graph | Cada resolución | `DeadlockDetector` | `DeadlockInfo` + Loki |
| Duplicados | Fingerprint SHA-256 | Cada registro | `DuplicateDetection` | `TaskRecord` + Loki |
| Latencia de resolución | `total_duration` en `ConflictResolutionResult` | Cada conflicto | `ConflictResolutionLayer` | Histograma Prometheus |
| Tasa de escalación | Ratio `escalation_total / (total conflictos)` | Ventana 10 min | `ObservabilityManager` | Grafana panel |
| Tasa de éxito negociación | Ratio `acuerdos / negociaciones` | Ventana 10 min | `ObservabilityManager` | Alerta `NegociacionBajaExito` |

### 12.5 Plan de contingencia UC-322

1. **Si circuit breaker se abre**: ejecutar IT-322.3 (análisis de causa raíz + reset manual).
2. **Si deadlock detectado**: ejecutar IT-322.5 (identificar ciclo, liberar agente de menor reputación).
3. **Si reputación de agente cae < 0.30**: alertar al equipo de UC-315 para evaluar desregistro del agente en CNP.
4. **Si tasa de escalación > 50%**: revisar thresholds de negociación y votación; posible `agreement_threshold` demasiado bajo.
5. **Si todos los niveles fallan repetidamente**: verificar calidad de datos de entrada (UC-315 perception pipeline).
6. **Si API no responde**: reiniciar servicio UC-322 y verificar logs Loki para error de inicio.

---

### 12.6 Diagrama de flujo de la iteración principal con UC-322

```text
       Entorno
          │
          ▼
   ┌──────────────┐
   │  MP-01       │ CentralBrain.observe()
   │  Percepción  │
   └──────────────┘
          │ snapshots
          ▼
   ┌──────────────┐
   │  MP-02       │ GlobalWorkspace.build_workspace()
   │  GWT         │ GlobalWorkspace.broadcast()
   └──────────────┘
          │ selected_hypothesis / broadcast
          ▼
   ┌──────────────┐
   │  MP-03       │ MetacognitiveMonitor.observe_internal_state()
   │  Monitor     │ → coherencia + veredicto
   └──────────────┘
          │ veredicto
          ▼
   ┌──────────────┐
   │  MP-04       │ ReActReasonactToTBrain.predict()
   │  ReAct + ToT │
   └──────────────┘
          │ predicción ask/bid
          ▼
   ┌──────────────┐
   │  MP-05       │ BDI + Juice + Safety
   │  Decisión    │ → propuestas de agentes
   └──────────────┘
          │ propuestas conflictivas
          ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                  MP-322 — UC-322                              │
   │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────┐│
   │  │ SP-322.1   │→ │ SP-322.2   │→ │ SP-322.3   │→ │SP-322.4││
   │  │ Negociación│  │ Votación   │  │ CNP        │  │Escalac.││
   │  └────────────┘  └────────────┘  └────────────┘  └────────┘│
   │  + SP-322.5 Reputación  + SP-322.6 Dup/Deadlock  + SP-322.7│
   └─────────────────────────────────────────────────────────────┘
          │ resolución + veredicto (evidencia)
          ▼
   ┌──────────────┐
   │  UC-324      │ PRE / EXEC / POST gates
   │  Contención  │ → autorización de acción
   └──────────────┘
          │ acción autorizada
          ▼
   ┌──────────────┐
   │  UC-317      │ AgentKernel
   │  Ejecución   │ LLM + Tools + Memory + Scheduler
   └──────────────┘
          │ resultado
          ▼
   ┌──────────────┐
   │  MP-06       │ ExchangeSimulator / WorldModel
   │  Feedback    │ → observaciones → SP-322.5 (reputación)
   └──────────────┘
          │
          ▼
   ┌──────────────┐
   │  MP-08/09    │ Autoevaluación + Plasticidad
   └──────────────┘
          │
          ▼
   ┌──────────────┐
   │  MP-12       │ SelfAwarenessLoop
   │  Narrativa   │
   └──────────────┘
          │
          ▼
   [Retorno al Entorno]
```

---

### 12.7 API REST UC-322

Servicio en `http://localhost:5322`. Archivo: <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/api_322.py" />

| Método | Endpoint | Subproceso | Descripción |
|---|---|---|---|
| GET | `/health` | — | Estado del servicio |
| GET | `/api/v1/schema` | — | Schemas de entrada/salida (INPUT_CARDS/OUTPUT_CARDS) |
| GET | `/` | — | Información del servicio y lista de endpoints |
| POST | `/api/v1/conflicts/resolve` | SP-322.1–4 | Resuelve un conflicto entre agentes |
| POST | `/api/v1/reputation/record` | SP-322.5 | Registra episodio y actualiza reputación |
| GET | `/api/v1/reputation/ranking` | SP-322.5 | Ranking de agentes por dominio |
| GET | `/api/v1/reputation/<agent_id>` | SP-322.5 | Reputación de un agente específico |
| POST | `/api/v1/duplicate/check` | SP-322.6 | Verifica si tarea es duplicado |
| POST | `/api/v1/deadlock/check` | SP-322.6 | Verifica deadlocks en wait graph |
| GET | `/api/v1/conflicts/history` | MP-322 | Historial de resoluciones |
| GET | `/api/v1/escalation/history` | SP-322.4 | Historial de escalaciones |
| GET | `/api/v1/escalation/circuit-breaker` | SP-322.7 | Estado del circuit breaker |
| POST | `/api/v1/escalation/circuit-breaker/reset` | SP-322.7 | Resetear circuit breaker |
| GET | `/api/v1/observability/summary` | SP-322.7 | Resumen de métricas, logs y trazas |
| GET | `/api/v1/observability/logs` | SP-322.7 | Logs estructurados (filtrable por level, trace_id) |
| GET | `/api/v1/observability/spans` | SP-322.7 | Trazas/spans |
| GET | `/metrics` | SP-322.7 | Exportación Prometheus |
| GET | `/api/v1/tasks/active` | SP-322.6 | Tareas activas registradas |

---

### 12.8 CLI y comandos

```bash
cd /Users/utron/Documents/code-books/TomoIII/UC-322/code

# Tests (no requiere PYTHONPATH — módulos UC-322 son independientes)
python3 -m pytest tests_uc322/ -q --tb=short

# Validación de los 4 procesos operacionales
python3 validate_uc322.py

# Demo CLI del sistema de resolución de conflictos
PYTHONPATH=../../UC-315/code python3 UC-322.py

# Servidor API REST (puerto 5322)
PYTHONPATH=../../UC-315/code python3 api_322.py
```

---

### 12.9 Estructura de archivos UC-322

```text
UC-322/code/
├── _import_paths.py             # Helper: agrega UC-315/code al sys.path
├── UC-322.py                    # ConflictResolutionLayer + demo CLI
├── uc322.py                     # Wrapper para importación (guión en nombre)
├── api_322.py                   # API REST Flask (18 endpoints)
├── conflict_models.py           # 5 enums + 10 dataclasses
├── reputation_system.py         # ReputationSystem + EpisodeRecord + ReputationEntry
├── negotiation_engine.py        # NegotiationEngine + NegotiationConfig
├── voting_system.py             # VotingSystem + VotingConfig
├── cnp_dynamic.py               # DynamicCNP + CNPConfig
├── escalation_protocol.py       # EscalationProtocol + EscalationConfig
├── duplicate_detection.py       # DuplicateDetection + DeadlockDetector
├── observability.py             # ObservabilityManager (Prometheus/Loki/Spans)
├── agent_validation_engine.py   # Motor de validación de agentes
├── validate_uc322.py            # Validación operacional (4 categorías)
├── generate_brain_image.py      # Generador del diagrama de arquitectura
├── notes.md                     # Notas de diseño: impacto en el cerebro AGI
├── prometheus.yml               # Configuración Prometheus
├── loki-config.yml              # Configuración Loki
├── alert_rules.yml              # 5 reglas de alertas
├── grafana_dashboard.json       # 12 paneles de dashboard
└── tests_uc322/
    ├── __init__.py
    └── test_uc322.py            # 85 tests unitarios + integración + API
```

---

### 12.10 Referencias UC-322

- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/UC-322.md" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/_import_paths.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/UC-322.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/uc322.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/api_322.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/conflict_models.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/reputation_system.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/negotiation_engine.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/voting_system.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/cnp_dynamic.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/escalation_protocol.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/duplicate_detection.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/observability.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/validate_uc322.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/prometheus.yml" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/alert_rules.yml" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/grafana_dashboard.json" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/tests_uc322/test_uc322.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/code/notes.md" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-322/agi_brain_architecture.png" />

### Cerebro AGI (UC-315 — referenciado, no copiado)

- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/juice_agents.py" /> — `_local_validate()` reemplazado por SP-322.1
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/trading_agents.py" /> — pesos estáticos reemplazados por SP-322.2
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/cnp_broadcast_middleware.py" /> — `reliability` estático reemplazado por SP-322.3
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/metacognitive_monitor.py" /> — `_map_verdict()` reemplazado por SP-322.4
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-315/code/global_workspace.py" /> — detección de duplicados agregada por SP-322.6
