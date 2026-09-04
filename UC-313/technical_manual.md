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
          │ selected_strategy / blocked
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
