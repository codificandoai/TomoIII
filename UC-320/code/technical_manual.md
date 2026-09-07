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

# UC-320 — Capa de Integración Hugging Face: Governance, AAA, Catálogo, Inferencia, Entrenamiento y Pipeline K8s

## 1. Alcance y objetivo

UC-320 es la **capa de integración y gobernanza entre Hugging Face y el
ecosistema AGI UTRON.ai** (UC-315 / UC-317 / UC-324). Su función es
permitir que usuarios autenticados con su identidad personal de
Hugging Face puedan:

- Descubrir, evaluar y descargar modelos, datasets y Spaces del Hub público.
- Ejecutar inferencia a través de Inference Providers, Endpoints y Spaces.
- Generar scripts de fine-tuning LoRA/QLoRA y ejecutar entrenamiento controlado.
- Publicar modelos reentrenados a su propia cuenta de Hugging Face.
- Desplegar workloads de inferencia y entrenamiento sobre Kubernetes on-premise.
- Operar bajo contención UC-324 (PRE/EXEC/POST gates) en cada acción sensible.

**Regla arquitectónica fundamental:**

> UC-315 decide, UC-317 ejecuta, UC-324 contiene, UC-320 integra Hugging Face.

**Principio de facturación:**

> Los cargos de GPU y compute de Hugging Face se asocian a la cuenta HF
> del usuario, no a UTRON.ai. UTRON.ai no almacena credenciales maestras.

**Principio de evidencia:**

> Un modelo genera evidencia. La evidencia no es una orden.

---

## 2. Glosario UC-320

| Término | Definición |
|---|---|
| **HF Token** | Token personal de Hugging Face (`hf_xxx`) enviado por el usuario en cada request. |
| **OAuth PKCE** | Proof Key for Code Exchange; extensión de OAuth 2.0 que evita interceptación del code. |
| **Gated Model** | Modelo que requiere aceptación explícita de términos antes de su descarga. |
| **PVC RWX** | PersistentVolumeClaim con accessMode `ReadWriteMany`; permite caché compartida entre Pods. |
| **CRD** | CustomResourceDefinition de Kubernetes (PyTorchJob, RayJob). |
| **LoRA** | Low-Rank Adaptation; técnica PEFT que entrena solo adaptadores de bajo rango. |
| **QLoRA** | Quantized LoRA; LoRA con cuantización 4-bit del modelo base. |
| **vLLM** | Servidor de inferencia optimizado con paged attention; expone `/v1/chat/completions`. |
| **TGI** | Text Generation Inference; servidor de Hugging Face para LLMs. |
| **Allowlist** | Lista interna de modelos aprobados para uso en UTRON.ai. |
| **SecureContract** | Contrato tipado entre UC-315/UC-317/UC-324 que describe la operación a ejecutar. |
| **Ephemeral Secret** | Secret de Kubernetes con TTL 1h que contiene el token HF del usuario. |
| **Garbage Collection** | Eliminación de Jobs, Deployments y Secrets de K8s tras completar el pipeline. |

---

## 3. Diagrama general de flujo (mapa de proceso macro UC-320)

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ENTRADAS                                           │
│   HF Token del usuario │ Request (sentiment/embed/classify/train/deploy)   │
│   Authorization: Bearer hf_xxx  o  X-HF-Token: hf_xxx                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-320.01  AUTENTICACIÓN Y AUTORIZACIÓN (AAA)                               │
│   hf_auth.authenticate() → UserSession → role → permissions                 │
│   hf_oauth.get_authorization_url() → exchange_code() → scoped token          │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-320.02  DESCUBRIMIENTO DE CATÁLOGO Y PANEL DE DECISIÓN                   │
│   hf_catalog.list_models/datasets/spaces() → filtrado → metadata            │
│   hf_model_panel.get_model_card_panel() → VRAM + license + K8s + benchmarks │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-320.03  INFERENCIA Y GENERACIÓN DE EVIDENCIA                            │
│   contracts.ContractBuilder → SecureContract                                │
│   uc324_gates.gate_pre() → gate_exec() → skills.*.run() → gate_post()       │
│   hf_gateway.chat() → evidence (no order)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-320.04  ENTRENAMIENTO, PEFT Y EVALUACIÓN                                │
│   training.submit() → run() → promote() (human + red-team approval)         │
│   hf_script_generator.generate_lora/qlora_script()                          │
│   hf_services.PEFTService.create_adapter() → save_adapter()                 │
│   hf_services.EvaluateService.compute() → compare()                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-320.05  PIPELINE K8s DE 6 PASOS                                         │
│   Paso 1: PKCE + JWT + Secret efímero                                       │
│   Paso 2: Pre-flight (VRAM vs cluster)                                      │
│   Paso 3: Manifest vLLM/PyTorchJob/RayJob + apply                           │
│   Paso 4: PVC RWX + cache SHA-256                                           │
│   Paso 5: Ejecución + métricas WebSocket                                    │
│   Paso 6: Package .safetensors + upload_folder() + GC                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-320.06  PUBLICACIÓN Y CICLO DE VIDA DEL MODELO                          │
│   ModelCardService.create() → approve() → push_to_hub()                     │
│   LineageTracker.register_derivation() → training_history                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MP-320.07  AUDITORÍA, FACTURACIÓN Y GOBERNANZA                             │
│   uc324_gates audit log → hf_gateway audit → /api/v1/audit                  │
│   Billing metadata: user_hf_username, charges_to_user_account               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Plan Maestro de Procesos (PMP) UC-320

| ID | Macro Proceso | Responsable | Entradas principales | Salidas principales | KPIs |
|---|---|---|---|---|---|
| MP-320.01 | Autenticación y Autorización (AAA) | `HFAuth`, `HFOAuth` | HF Token, OAuth code | `UserSession`, scoped token, role | Latencia auth, tasa 401/403 |
| MP-320.02 | Descubrimiento de catálogo y panel de decisión | `HFCatalogBrowser`, `ModelPanel` | Filtros (task, license, author), model_id | `CatalogItem[]`, VRAM, license, K8s manifest, benchmarks | Cache hit ratio, latencia de catálogo |
| MP-320.03 | Inferencia y generación de evidencia | `UC320Orchestrator`, `skills.*`, `uc324_gates` | Prompt, model_id, contract | `SentimentEvidence`, `EmbeddingResult`, `ClassificationResult` | Latencia P95, tasa de bloqueo PRE/POST |
| MP-320.04 | Entrenamiento, PEFT y evaluación | `TrainingManager`, `PEFTService`, `EvaluateService`, `ScriptGenerator` | Dataset, base_model, hyperparams | `TrainingJob`, LoRA adapter, metrics | Tasa de éxito, VRAM training, tokens/sec |
| MP-320.05 | Pipeline K8s de 6 pasos | `K8sPipeline`, `K8sManifestBuilder`, `SharedCacheManager` | model_id, operation, gpu_type | Deployment/Job YAML, metrics, published model | Tiempo end-to-end, cache hit, OOM evitado |
| MP-320.06 | Publicación y ciclo de vida del modelo | `ModelCardService`, `HubPublisher`, `LineageTracker` | Adapter/model, README, user token | HF repo publicado, lineage tree | Tasa de push exitoso, tiempo de publicación |
| MP-320.07 | Auditoría, facturación y gobernanza | `UC324GateIntegrator`, `HFAuth`, `api_320` | Toda operación | Audit log, billing metadata | Cobertura de audit, precisión de billing |

---

## 5. Descripción de macro procesos y subprocesos

### MP-320.01 — Autenticación y Autorización (AAA)

**Propósito:** Validar la identidad del usuario contra Hugging Face, establecer
una sesión con rol y permisos, y garantizar que cada request opera con el
token personal del usuario — nunca con una credencial maestra de UTRON.

**Archivos clave:**
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_auth.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_oauth.py" />

**Entradas:**
- Header `Authorization: Bearer hf_xxx` o `X-HF-Token: hf_xxx`.
- OAuth: `client_id`, `client_secret`, `redirect_uri`, `code`, `state`, `code_verifier`.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.01.1 | `extract_hf_token()` | Extrae token de headers HTTP. | `str` token |
| SP-320.01.2 | `HFAuth.authenticate()` | Valida token con `whoami` (real) o mock users (test). | `UserSession` |
| SP-320.01.3 | `HFAuth.authorize()` | Verifica que el rol del usuario tiene el permiso requerido. | `bool` |
| SP-320.01.4 | `require_permission()` | Decorador Flask que bloquea 403 si falta permiso. | Response 403 |
| SP-320.01.5 | `HFOAuth.get_authorization_url()` | Construye URL OAuth con `state` anti-CSRF y scopes. | URL de autorización |
| SP-320.01.6 | `HFOAuth.exchange_code()` | Intercambia `code` por `access_token` + `userinfo`. | `OAuthUserInfo` |
| SP-320.01.7 | `HFOAuth.validate_scopes()` | Verifica que los scopes concedidos incluyen los requeridos. | `bool` |
| SP-320.01.8 | `init_auth()` | Middleware `before_request` que pobla `g.user_session`. | Contexto Flask |

**Roles y permisos:**

| Rol | Permisos clave |
|---|---|
| `viewer` | `inference:read`, `catalog:browse`, `models:download`, `datasets:read`, `spaces:read`, `model_cards:read` |
| `user` | + `models:adapt`, `datasets:load`, `spaces:create`, `benchmark:run` |
| `developer` | + `models:train`, `models:push`, `datasets:transform`, `endpoints:*`, `spaces:stop`, `model_cards:*`, `evaluate:compute` |
| `admin` | Todos los permisos, incluyendo `training:promote`, `endpoints:delete`, `spaces:delete` |

**Scopes OAuth:**

| Scope | Tipo | Propósito |
|---|---|---|
| `openid` | Requerido | Identidad federada |
| `profile` | Requerido | Datos de perfil |
| `email` | Requerido | Correo del usuario |
| `read-repos` | Requerido | Lectura de repos públicos/privados |
| `inference-api` | Requerido | Inferencia serverless |
| `write-repos` | Opcional | Publicar modelos/adapters |
| `compute` | Opcional | GPU charges a cuenta del usuario |

**Salidas:**
- `UserSession` con `session_id`, `hf_username`, `role`, `expires_at`.
- Token propagado a todos los servicios HF posteriores.
- Sesión cacheada para evitar re-autenticación por request.

---

### MP-320.02 — Descubrimiento de catálogo y panel de decisión

**Propósito:** Permitir al usuario explorar el catálogo público de
Hugging Face (modelos, datasets, Spaces), obtener metadata detallada,
calcular VRAM, analizar licencias, generar manifiestos K8s y comparar
benchmarks — todo en un panel interactivo de decisión.

**Archivos clave:**
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_catalog.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_model_panel.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/model_catalog.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_download.py" />

**Entradas:**
- Filtros: `task`, `search`, `license`, `author`, `sort`, `direction`, `limit`.
- `model_id` para panel detallado.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.02.1 | `HFCatalogBrowser.list_models()` | Lista modelos con filtros y cache TTL 5 min. | `List[CatalogItem]` |
| SP-320.02.2 | `HFCatalogBrowser.list_datasets()` | Lista datasets con filtros. | `List[CatalogItem]` |
| SP-320.02.3 | `HFCatalogBrowser.list_spaces()` | Lista Spaces con filtros. | `List[CatalogItem]` |
| SP-320.02.4 | `HFCatalogBrowser.get_model()` | Obtiene metadata completa de un modelo. | `Dict` metadata |
| SP-320.02.5 | `HFCatalogBrowser.check_gated()` | Verifica si un modelo es gated y si el usuario tiene acceso. | `Dict` gated status |
| SP-320.02.6 | `HFCatalogBrowser.search_all()` | Búsqueda global cross-asset. | `Dict` models+datasets+spaces |
| SP-320.02.7 | `VRAMCalculator.estimate_all_modes()` | Calcula VRAM para FP32/FP16/INT8/INT4 × inference/full/LoRA. | `Dict` por modo |
| SP-320.02.8 | `LicenseAnalyzer.analyze()` | Clasifica licencia: green/yellow/red + commercial_use. | `Dict` license |
| SP-320.02.9 | `K8sManifestGenerator.generate_full_deploy()` | Genera YAML vLLM/TGI para K8s. | `str` YAML |
| SP-320.02.10 | `BenchmarkAnalyzer.get_benchmarks()` | Recupera benchmarks reales/estimados del modelo. | `Dict` metrics |
| SP-320.02.11 | `LineageTracker.get_lineage()` | Construye árbol de derivación del modelo. | `Dict` lineage |
| SP-320.02.12 | `PlaygroundFinder.find_spaces()` | Encuentra Spaces oficiales para probar el modelo. | `List` spaces |
| SP-320.02.13 | `ModelPanel.get_model_card_panel()` | Agrega todas las features en un panel unificado. | `Dict` panel completo |
| SP-320.02.14 | `HFDownloadManager.resolve_url()` | Construye URL directa de descarga + curl command. | `Dict` URL |
| SP-320.02.15 | `HFDownloadManager.get_all_snippets()` | Genera snippets de código (transformers, diffusers, datasets, hub). | `Dict` snippets |
| SP-320.02.16 | `ModelCatalog.is_allowed()` | Verifica que el modelo está en la allowlist interna. | `bool` |

**Salidas:**
- Listas filtradas de modelos/datasets/Spaces con metadata.
- Panel de decisión con VRAM, licencia, K8s YAML, benchmarks, lineage, playground.
- URLs de descarga directa y snippets de código.
- Detección de modelos gated.

---

### MP-320.03 — Inferencia y generación de evidencia

**Propósito:** Ejecutar inferencia (sentiment, embedding, clasificación)
sobre modelos de Hugging Face, pasando por los tres gates de contención
UC-324 (PRE/EXEC/POST) y produciendo **evidencia** que UC-315 puede
consumir — nunca una orden autónoma.

**Archivos clave:**
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/orchestrator.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/contracts.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/uc324_gates.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/skills.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_gateway.py" />

**Entradas:**
- `prompt` o `text`, `model_id`, `user_token`.
- `SecureContract` construido por `ContractBuilder`.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.03.1 | `ContractBuilder.sentiment_inference()` | Construye `SecureContract` con modelo, input, output schema. | `SecureContract` |
| SP-320.03.2 | `UC324GateIntegrator.gate_pre()` | Valida allowlist, prompt injection, PII, cost/latency. | `GateResult[]` |
| SP-320.03.3 | `UC324GateIntegrator.gate_exec()` | Firma HMAC + nonce + anti-replay + shell injection check. | `GateResult[]` |
| SP-320.03.4 | `MarketSentimentSkill.run()` | Ejecuta `HuggingFaceModelGateway.chat()` con el token del usuario. | `SentimentEvidence` |
| SP-320.03.5 | `SemanticEmbeddingSkill.run()` | Genera embedding del texto de entrada. | `EmbeddingResult` |
| SP-320.03.6 | `ZeroShotClassificationSkill.run()` | Clasifica el texto contra labels candidatas. | `ClassificationResult` |
| SP-320.03.7 | `UC324GateIntegrator.gate_post()` | Verifica output no vacío, no PII leak, no tool injection. | `GateResult[]` |
| SP-320.03.8 | `UC324GateIntegrator.evaluate()` | Agrega los tres gates en `ContainmentDecision`. | `ContainmentDecision` |
| SP-320.03.9 | `HuggingFaceModelGateway.chat()` | Llama a InferenceClient con token del usuario (real o mock). | `str` respuesta |

**Flujo de gates:**

```text
Request → ContractBuilder → SecureContract
    │
    ▼
GATE PRE (uc324_gates)
    │ allowlist? prompt injection? PII? cost? latency?
    ├── BLOCK → 403 + audit
    │
    ▼ ALLOW
GATE EXEC (uc324_gates)
    │ HMAC nonce? shell injection?
    ├── BLOCK → 403 + audit
    │
    ▼ ALLOW
Skill.run() → HuggingFaceModelGateway.chat(token=user)
    │
    ▼
GATE POST (uc324_gates)
    │ output vacío? PII leak? tool injection?
    ├── BLOCK → 500 + audit + rollback
    │
    ▼ ALLOW
Evidence → UC-315 (evidencia, no orden)
    │
    ▼
Audit log persistido
```

**Salidas:**
- `SentimentEvidence` / `EmbeddingResult` / `ClassificationResult`.
- `ContainmentDecision` con veredicto agregado.
- Audit log con trace_id, user, model, latencia, cost.

---

### MP-320.04 — Entrenamiento, PEFT y evaluación

**Propósito:** Gestionar el ciclo de vida de entrenamiento de modelos:
someter jobs, ejecutarlos con aprobación humana y red-team, generar
scripts LoRA/QLoRA, crear adaptadores PEFT y evaluar métricas.

**Archivos clave:**
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/training.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_script_generator.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_services.py" /> (PEFTService, EvaluateService, TrainerService, DatasetManager)

**Entradas:**
- `base_model`, `dataset_id`, `hyperparams`, `method` (lora/qlora/full).
- `human_approved`, `red_team_status` para promoción.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.04.1 | `TrainingManager.submit()` | Crea `TrainingJob` en estado `pending`. | `TrainingJob` |
| SP-320.04.2 | `TrainingManager.run()` | Ejecuta entrenamiento (stub determinista o Trainer real). | `TrainingJob` completed |
| SP-320.04.3 | `TrainingManager.promote()` | Promueve a producción; requiere `human_approved=True` + `red_team_status="passed"`. | `bool` |
| SP-320.04.4 | `ScriptGenerator.generate_lora_script()` | Genera script Python PEFT/LoRA completo. | `str` script |
| SP-320.04.5 | `ScriptGenerator.generate_qlora_script()` | Genera script QLoRA 4-bit. | `str` script |
| SP-320.04.6 | `ScriptGenerator.generate_notebook()` | Genera Jupyter notebook `.ipynb`. | `str` JSON |
| SP-320.04.7 | `DatasetManager.load()` | Carga dataset desde HF con `load_dataset`. | `Dataset` |
| SP-320.04.8 | `DatasetManager.validate_for_training()` | Valida schema y formato del dataset. | `Dict` |
| SP-320.04.9 | `DatasetManager.transform()` | Aplica transformación al dataset. | `Dataset` |
| SP-320.04.10 | `TrainerService.train()` | Ejecuta `Trainer` con `TrainingArguments`. | `Dict` job status |
| SP-320.04.11 | `PEFTService.create_adapter()` | Crea adaptador LoRA sobre modelo base. | `Dict` adapter |
| SP-320.04.12 | `PEFTService.save_adapter()` | Guarda adaptador en HF Hub con token del usuario. | `str` repo URL |
| SP-320.04.13 | `EvaluateService.compute()` | Calcula métrica con `evaluate.load`. | `Dict` metric |
| SP-320.04.14 | `EvaluateService.compare()` | Compara métricas entre modelos. | `Dict` comparison |
| SP-320.04.15 | `ModelBenchmark.benchmark()` | Benchmark paralelo de múltiples modelos. | `List[BenchmarkResult]` |

**Estados de TrainingJob:**

```text
pending → running → evaluating → completed
                ↓              ↓
            blocked        failed
```

**Salidas:**
- `TrainingJob` con status, metrics, model_path.
- Script Python + notebook Jupyter listos para ejecutar.
- LoRA adapter publicado en HF Hub del usuario.
- Métricas de evaluación reproducibles.

---

### MP-320.05 — Pipeline K8s de 6 pasos

**Propósito:** Ejecutar el ciclo completo de despliegue de un modelo
sobre Kubernetes on-premise: desde la autenticación OAuth/PKCE hasta
la publicación del modelo reentrenado y la limpieza de recursos.

**Archivo clave:** <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_k8s_pipeline.py" />

**Entradas:**
- `model_id`, `operation` (inference/training), `gpu_type`, `user_token`.
- `dataset_id` (si es entrenamiento).

#### Paso 1 — Autenticación, PKCE y Secret efímero

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.05.1.1 | `PKCEVerifier.generate_pair()` | Genera `code_verifier` + `code_challenge` (SHA256 + BASE64URL). | PKCE pair |
| SP-320.05.1.2 | `JWTValidator.validate()` | Valida JWT del usuario contra HF oauth/userinfo. | `Dict` claims |
| SP-320.05.1.3 | `SecretManager.create_secret()` | Crea K8s Secret efímero con token HF del usuario (TTL 1h). | `K8sSecret` |
| SP-320.05.1.4 | `SecretManager.delete_secret()` | Elimina Secret al expirar o completar el pipeline. | `bool` |

#### Paso 2 — Descubrimiento de artefactos y pre-flight

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.05.2.1 | `HFCatalogBrowser.get_model()` | Obtiene metadata: archivos, tamaño, formato. | `Dict` metadata |
| SP-320.05.2.2 | `VRAMCalculator.estimate()` | Calcula VRAM mínimo para el modo solicitado. | `Dict` vram |
| SP-320.05.2.3 | `K8sClusterValidator.list_nodes()` | Lista nodos GPU del clúster. | `List[K8sNodeResources]` |
| SP-320.05.2.4 | `K8sClusterValidator.pre_flight_check()` | Verifica VRAM disponible vs requerido; previene OOM. | `Dict` can_proceed |

#### Paso 3 — Generación de manifiestos y provisioning

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.05.3.1 | `K8sManifestBuilder.build_vllm_deployment()` | Genera Deployment + Service vLLM con env vars HF. | `str` YAML |
| SP-320.05.3.2 | `K8sManifestBuilder.build_pytorchjob_crd()` | Genera PyTorchJob CRD (Kubeflow). | `str` YAML |
| SP-320.05.3.3 | `K8sManifestBuilder.build_rayjob_crd()` | Genera RayJob CRD (KubeRay). | `str` YAML |
| SP-320.05.3.4 | `K8sManifestBuilder.build_pvc()` | Genera PVC ReadWriteMany para caché compartida. | `str` YAML |
| SP-320.05.3.5 | `K8sAPIClient.apply_manifest()` | Aplica manifiesto al clúster via Kubernetes API. | `Dict` result |

**Variables de entorno inyectadas:**

| Variable | Valor | Propósito |
|---|---|---|
| `HUGGING_FACE_HUB_TOKEN` | Secret del usuario | Autenticación HF |
| `HF_HUB_ENABLE_HF_TRANSFER` | `1` | Descarga Rust multihilo |
| `HF_HOME` | `/root/.cache/huggingface` | Caché en PVC compartido |

#### Paso 4 — PVC compartido y caché SHA-256

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.05.4.1 | `SharedCacheManager.check_cache()` | Verifica si el blob ya está en caché (SHA-256). | `Dict` hit/miss |
| SP-320.05.4.2 | `SharedCacheManager.prefetch_model()` | Descarga modelo al PVC si cache miss. | `Dict` result |
| SP-320.05.4.3 | `SharedCacheManager.list_cache()` | Lista blobs en caché. | `List` |

#### Paso 5 — Ejecución y métricas en tiempo real

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.05.5.1 | `K8sAPIClient.apply_manifest()` | Aplica Deployment/Job al clúster. | `Dict` |
| SP-320.05.5.2 | `MetricsStreamer.simulate_training_metrics()` | Emite métricas: loss, tokens/sec, VRAM, GPU util. | `JobMetrics` |
| SP-320.05.5.3 | `MetricsStreamer.subscribe()` | Suscripción WebSocket para métricas live. | `str` sub_id |
| SP-320.05.5.4 | `MetricsStreamer.get_metrics_history()` | Historial de métricas por job. | `List[JobMetrics]` |

#### Paso 6 — Publicación y garbage collection

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.05.6.1 | `ModelPackager.package()` | Serializa adapter como `.safetensors` + `README.md`. | `Dict` package |
| SP-320.05.6.2 | `HubPublisher.upload_folder()` | Publica a HF Hub con `upload_folder()` + token del usuario. | `str` repo URL |
| SP-320.05.6.3 | `GarbageCollector.cleanup_job()` | Elimina Job + Secret + libera GPUs. | `Dict` cleanup |

#### Orquestador del pipeline

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.05.7 | `K8sPipeline.execute_pipeline()` | Ejecuta los 6 pasos en secuencia con manejo de errores. | `Dict` pipeline result |

**Salidas del pipeline completo:**
- Deployment/Job desplegado en K8s.
- Modelo publicado en HF Hub del usuario.
- GPUs liberadas tras completar.
- Audit trail completo de los 6 pasos.

---

### MP-320.06 — Publicación y ciclo de vida del modelo

**Propósito:** Gestionar la publicación de modelos reentrenados en
Hugging Face Hub, incluyendo model cards, aprobación, linaje y
historial de reentrenamiento.

**Archivos clave:**
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_services.py" /> (ModelCardService)
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_model_panel.py" /> (LineageTracker)

**Entradas:**
- `model_id`, `README.md` content, `user_token`.
- `parent_model`, `derivation_type` para linaje.

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.06.1 | `ModelCardService.create()` | Crea model card con metadata y README. | `ModelCard` |
| SP-320.06.2 | `ModelCardService.approve()` | Aprueba model card (rol `model_cards:approve`). | `bool` |
| SP-320.06.3 | `ModelCardService.push_to_hub()` | Publica model card a HF Hub con token del usuario. | `str` URL |
| SP-320.06.4 | `ModelCardService.get_markdown()` | Renderiza model card como markdown. | `str` markdown |
| SP-320.06.5 | `LineageTracker.register_derivation()` | Registra relación parent → derived. | `Dict` |
| SP-320.06.6 | `LineageTracker.get_lineage()` | Construye árbol de derivación. | `Dict` tree |
| SP-320.06.7 | `LineageTracker.get_training_history()` | Historial de reentrenamientos. | `List` |

**Salidas:**
- Model card publicado en HF Hub del usuario.
- Árbol de linaje con relaciones base → SFT → merge → fine-tuned.
- Historial de reentrenamientos con hiperparámetros y métricas.

---

### MP-320.07 — Auditoría, facturación y gobernanza

**Propósito:** Registrar toda operación sensible para auditoría,
asociar cargos de GPU/compute a la cuenta HF del usuario y mantener
gobernanza sobre el ecosistema.

**Archivos clave:**
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/uc324_gates.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_gateway.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_auth.py" />

**Subprocesos:**

| SP | Nombre | Actividad | Salida |
|---|---|---|---|
| SP-320.07.1 | `UC324GateIntegrator` audit | Registra cada gate PRE/EXEC/POST con trace_id. | Audit entry |
| SP-320.07.2 | `HuggingFaceModelGateway` audit | Registra cada llamada a HF con model, tokens, latencia, cost. | Audit entry |
| SP-320.07.3 | Billing metadata | Asocia `user_hf_username` a cada operación de GPU/compute. | Billing tag |
| SP-320.07.4 | `/api/v1/audit` | Expone audit log vía API (rol `catalog:browse`). | `List` entries |
| SP-320.07.5 | `/api/v1/auth/sessions` | Lista sesiones activas (rol `admin`). | `List` sessions |

**Principio de facturación:**

> Toda operación que involucre GPU o compute de Hugging Face se etiqueta
> con `billing_account = user_hf_username`. UTRON.ai no absorbe cargos
> de compute del usuario. Los cargos por descarga de modelos públicos
> desde el CDN de HF son $0.

**Salidas:**
- Audit log persistente con trazabilidad completa.
- Metadata de facturación por operación.
- Sesiones activas monitorizables.

---

## 6. Mapa de iteraciones y llamados entre módulos

### 6.1 Flujo principal de inferencia

```text
Usuario (HF Token)
    │
    ▼
api_320.py (Flask route)
    │
    ├── init_auth() → g.user_session
    ├── require_permission("inference:read")
    │
    ▼
orchestrator.UC320Orchestrator
    │
    ├── ContractBuilder.sentiment_inference() → SecureContract
    │
    ├── UC324GateIntegrator.gate_pre(contract)
    │       └── allowlist? prompt injection? PII? cost?
    │
    ├── UC324GateIntegrator.gate_exec(contract)
    │       └── HMAC? nonce? shell injection?
    │
    ├── MarketSentimentSkill.run(prompt, token)
    │       └── HuggingFaceModelGateway.chat(model, prompt, token)
    │               └── InferenceClient (real) o mock
    │
    ├── UC324GateIntegrator.gate_post(output)
    │       └── output vacío? PII leak? tool injection?
    │
    └── OrchestratorResult(evidence, audit, billing)
            │
            ▼
        Response JSON → Usuario
```

### 6.2 Flujo del pipeline K8s

```text
Usuario (HF Token + model_id + operation)
    │
    ▼
/api/v1/pipeline/execute
    │
    ▼
K8sPipeline.execute_pipeline()
    │
    ├── Paso 1: PKCEVerifier + JWTValidator + SecretManager.create_secret()
    ├── Paso 2: HFCatalogBrowser.get_model() + VRAMCalculator + K8sClusterValidator.pre_flight_check()
    ├── Paso 3: K8sManifestBuilder.build_*() + K8sAPIClient.apply_manifest()
    ├── Paso 4: SharedCacheManager.check_cache() + prefetch_model()
    ├── Paso 5: K8sAPIClient.apply_manifest() + MetricsStreamer.simulate_training_metrics()
    └── Paso 6: ModelPackager.package() + HubPublisher.upload_folder() + GarbageCollector.cleanup_job()
            │
            ▼
        Pipeline result (6 steps, billing, audit)
```

### 6.3 Llamados entre capas

| Origen | Destino | Método / Flujo | Propósito |
|---|---|---|---|
| `api_320` | `hf_auth` | `init_auth()`, `require_permission()` | Middleware AAA |
| `api_320` | `orchestrator` | `orch.sentiment()`, `orch.embedding()` | Inferencia |
| `api_320` | `hf_services` | `HFServices.*` | 8 servicios HF |
| `api_320` | `hf_k8s_pipeline` | `K8sPipeline.execute_pipeline()` | Pipeline K8s |
| `api_320` | `hf_oauth` | `HFOAuth.get_authorization_url()` | OAuth login |
| `orchestrator` | `contracts` | `ContractBuilder.*` | Construir contrato |
| `orchestrator` | `uc324_gates` | `gate_pre/exec/post()` | Contención |
| `orchestrator` | `skills` | `*Skill.run()` | Ejecutar skill |
| `orchestrator` | `hf_gateway` | `HuggingFaceModelGateway.chat()` | Llamada HF |
| `orchestrator` | `training` | `TrainingManager.*` | Entrenamiento |
| `orchestrator` | `hf_catalog` | `HFCatalogBrowser.*` | Catálogo |
| `orchestrator` | `hf_download` | `HFDownloadManager.*` | Descargas |
| `orchestrator` | `hf_script_generator` | `ScriptGenerator.*` | Scripts |
| `orchestrator` | `templates` | `TemplateRegistry.*` | Plantillas |
| `orchestrator` | `model_catalog` | `ModelCatalog.is_allowed()` | Allowlist |
| `skills` | `hf_gateway` | `gateway.chat()` | Inferencia HF |
| `hf_k8s_pipeline` | `hf_model_panel` | `VRAMCalculator.estimate()` | Cálculo VRAM |
| `hf_k8s_pipeline` | `hf_catalog` | `HFCatalogBrowser.get_model()` | Metadata |
| `uc324_gates` | `model_catalog` | `is_allowed()` | Validar allowlist |

---

## 7. Plan de Control UC-320

### 7.1 Variables críticas y controles

| Variable | Método de control | Frecuencia | Responsable | Registro / Evidencia |
|---|---|---|---|---|
| Token HF válido | `HFAuth.authenticate()` con `whoami` | Cada request | `HFAuth` | `UserSession` |
| Permiso de operación | `require_permission()` decorator | Cada request | `HFAuth` | Response 200/403 |
| Allowlist de modelos | `ModelCatalog.is_allowed()` | Cada inferencia | `UC324GateIntegrator` | `GateResult` PRE |
| Prompt injection | `UC324GateIntegrator.gate_pre()` | Cada inferencia | `uc324_gates` | `GateResult` PRE |
| PII en input/output | `gate_pre()` + `gate_post()` | Cada inferencia | `uc324_gates` | `GateResult` |
| Costo por request | Contract `_estimated_cost` | Cada inferencia | `contracts` | Audit log |
| Latencia | Contract `_estimated_latency` | Cada inferencia | `contracts` | Audit log |
| HMAC anti-replay | `gate_exec()` | Cada ejecución | `uc324_gates` | `GateResult` EXEC |
| Output no vacío | `gate_post()` | Cada inferencia | `uc324_gates` | `GateResult` POST |
| Aprobación humana para promoción | `TrainingManager.promote()` | Cada promoción | `training` | `TrainingJob` |
| Red-team status | `promote()` requiere `passed` | Cada promoción | `training` | `TrainingJob` |
| VRAM pre-flight | `K8sClusterValidator.pre_flight_check()` | Cada pipeline | `hf_k8s_pipeline` | `PreFlightCheck` |
| Cache SHA-256 | `SharedCacheManager.check_cache()` | Cada pipeline | `hf_k8s_pipeline` | Cache entry |
| Secret TTL | `SecretManager` auto-cleanup 1h | Continuo | `hf_k8s_pipeline` | Secret deleted |
| Garbage collection | `GarbageCollector.cleanup_job()` | Cada pipeline | `hf_k8s_pipeline` | Cleanup log |
| Billing metadata | `user_hf_username` en audit | Cada operación | `hf_auth` | Audit entry |
| OAuth state anti-CSRF | `OAuthState` con TTL | Cada OAuth | `hf_oauth` | State validado |
| Scopes concedidos | `HFOAuth.validate_scopes()` | Cada OAuth | `hf_oauth` | Scopes list |

### 7.2 Plan de contingencia / rollback

1. **Gate PRE bloquea** → 403 + audit. No se ejecuta nada.
2. **Gate EXEC bloquea** → 403 + audit. No se ejecuta la skill.
3. **Gate POST bloquea** → 500 + audit + rollback de efectos secundarios.
4. **Pre-flight check falla** → Pipeline aborta en paso 2. No se crea manifiesto.
5. **Cache miss + descarga falla** → Reintento con backoff. Si persiste, aborta paso 4.
6. **Job K8s falla** → MetricsStreamer registra error. GarbageCollector limpia recursos.
7. **upload_folder() falla** → Package se preserva localmente. Reintento manual.
8. **Secret expira** → Pipeline aborta. Usuario debe re-autenticar.
9. **TrainingJob degradado** → `promote()` bloqueado. Requiere revisión humana.

---

## 8. Instructivos de trabajo

### 8.1 Instructivo de autenticación con HF Token (WI-320-01)

**Propósito:** Autenticar al usuario con su token personal de Hugging Face.

**Pasos:**
1. El usuario incluye `Authorization: Bearer hf_xxx` en cada request.
2. `init_auth()` middleware extrae el token con `extract_hf_token()`.
3. `HFAuth.authenticate()` valida el token contra `whoami` (producción) o mock users (test).
4. Se crea `UserSession` con `session_id`, `hf_username`, `role`, `expires_at`.
5. La sesión se cachea para evitar re-autenticación en requests subsecuentes.
6. Si el token es inválido → `401 Unauthorized`.
7. Si el token es válido pero falta permiso → `403 Forbidden`.

**Evidencia:** `UserSession` persistida en cache. Audit log con `trace_id`.

---

### 8.2 Instructivo de OAuth 2.0 con PKCE (WI-320-02)

**Propósito:** Realizar login OAuth con Hugging Face usando PKCE.

**Pasos:**
1. Frontend llama `GET /api/v1/auth/oauth/login`.
2. Backend genera `state` anti-CSRF y `code_verifier` + `code_challenge` (PKCE).
3. Backend retorna URL de autorización: `https://huggingface.co/oauth/authorize?...`.
4. Usuario redirige a HF, autoriza, HF redirige a `/api/v1/auth/oauth/callback?code=xxx&state=xxx`.
5. Backend valida `state` contra el generado.
6. Backend intercambia `code` + `code_verifier` por `access_token` via `exchange_code()`.
7. Backend valida scopes concedidos vs requeridos.
8. Backend crea `UserSession` y retorna token de sesión al frontend.

**Evidencia:** `OAuthUserInfo` con `sub`, `name`, `email`, `scopes`.

---

### 8.3 Instructivo de inferencia con gates UC-324 (WI-320-03)

**Propósito:** Ejecutar inferencia pasando por los tres gates de contención.

**Pasos:**
1. Construir `SecureContract` con `ContractBuilder`.
2. Ejecutar `gate_pre()`: validar allowlist, prompt injection, PII, cost, latency.
3. Si PRE bloquea → retornar 403 + audit. No continuar.
4. Ejecutar `gate_exec()`: validar HMAC, nonce, shell injection.
5. Si EXEC bloquea → retornar 403 + audit. No continuar.
6. Ejecutar `Skill.run()` → `HuggingFaceModelGateway.chat()` con token del usuario.
7. Ejecutar `gate_post()`: validar output no vacío, no PII leak, no tool injection.
8. Si POST bloquea → retornar 500 + audit + rollback.
9. Retornar evidence al usuario. La evidence **no es una orden**.

**Evidencia:** `ContainmentDecision` + audit log con trace_id.

---

### 8.4 Instructivo de exploración de catálogo (WI-320-04)

**Propósito:** Navegar el catálogo público de Hugging Face con filtros.

**Pasos:**
1. Llamar `GET /api/v1/catalog/models?task=text-generation&limit=20`.
2. `HFCatalogBrowser` consulta `https://huggingface.co/api/models` con filtros.
3. Cache TTL 5 min evita llamadas repetidas.
4. Para metadata detallada: `GET /api/v1/catalog/models/<model_id>`.
5. Para modelos gated: `GET /api/v1/catalog/models/<model_id>/gated`.
6. Para búsqueda global: `GET /api/v1/catalog/search?q=financial`.

**Evidencia:** `List[CatalogItem]` con metadata.

---

### 8.5 Instructivo de panel de decisión de modelo (WI-320-05)

**Propósito:** Obtener el panel completo de decisión para un modelo.

**Pasos:**
1. Llamar `GET /api/v1/panel/<model_id>`.
2. `ModelPanel.get_model_card_panel()` agrega:
   - VRAM para todos los modos (FP32/FP16/INT8/INT4 × inference/full/LoRA).
   - Licencia (green/yellow/red) + commercial_use.
   - K8s YAML manifiesto vLLM.
   - Benchmarks (tokens/sec, latency, throughput).
   - Linaje (parent, derived, base/SFT/merge).
   - Playground (Spaces oficiales).
3. Para VRAM específico: `POST /api/v1/panel/<model_id>/vram/estimate`.
4. Para comparar benchmarks: `POST /api/v1/panel/benchmarks/compare`.

**Evidencia:** `Dict` panel completo.

---

### 8.6 Instructivo de generación de script de fine-tuning (WI-320-06)

**Propósito:** Generar script LoRA/QLoRA listo para ejecutar.

**Pasos:**
1. Llamar `POST /api/v1/finetune/generate` con `base_model`, `dataset_id`, `method`.
2. `ScriptGenerator.generate()` produce:
   - Script Python completo con PEFT/LoRA o QLoRA.
   - Notebook Jupyter `.ipynb`.
   - Metadata con hiperparámetros.
3. El script incluye `push_to_hub()` con token del usuario.
4. Entregar script + notebook al usuario.

**Evidencia:** `Dict` con `script`, `notebook`, `metadata`.

---

### 8.7 Instructivo de entrenamiento y promoción (WI-320-07)

**Propósito:** Someter, ejecutar y promover un modelo reentrenado.

**Pasos:**
1. `POST /api/v1/training/submit` con `base_model`, `dataset_id`, `hyperparams`.
2. `TrainingManager.submit()` crea job en estado `pending`.
3. `POST /api/v1/training/run` con `job_id`.
4. `TrainingManager.run()` ejecuta entrenamiento (stub o Trainer real).
5. Job pasa a `completed` con métricas.
6. `POST /api/v1/training/promote` con `human_approved=True`, `red_team_status="passed"`.
7. `TrainingManager.promote()` valida aprobaciones y promueve.

**Evidencia:** `TrainingJob` con status, metrics, model_path.

---

### 8.8 Instructivo de pipeline K8s completo (WI-320-08)

**Propósito:** Ejecutar el pipeline de 6 pasos sobre Kubernetes.

**Pasos:**
1. Llamar `POST /api/v1/pipeline/execute` con `model_id`, `operation`, `gpu_type`.
2. **Paso 1:** Generar PKCE, validar JWT, crear Secret efímero con token HF.
3. **Paso 2:** Obtener metadata del modelo, calcular VRAM, pre-flight check vs cluster.
4. **Paso 3:** Generar manifiesto (vLLM/PyTorchJob/RayJob), aplicar al clúster.
5. **Paso 4:** Verificar caché SHA-256. Si miss, prefetch al PVC RWX.
6. **Paso 5:** Aplicar manifiesto, iniciar métricas WebSocket (loss, tokens/sec, VRAM).
7. **Paso 6:** Serializar `.safetensors`, `upload_folder()` a HF del usuario, GC de K8s.

**Evidencia:** `Dict` con 6 steps, billing, audit, repo URL publicado.

---

### 8.9 Instructivo de publicación de model card (WI-320-09)

**Propósito:** Crear, aprobar y publicar un model card en HF Hub.

**Pasos:**
1. `POST /api/v1/model-cards` con `model_id`, `content`, `metadata`.
2. `ModelCardService.create()` genera el model card.
3. `POST /api/v1/model-cards/<model_id>/approve` (rol `model_cards:approve`).
4. `POST /api/v1/model-cards/<model_id>/push` con token del usuario.
5. `ModelCardService.push_to_hub()` publica en HF Hub del usuario.

**Evidencia:** URL del repo publicado en HF Hub.

---

### 8.10 Instructivo de descarga directa (WI-320-10)

**Propósito:** Obtener URL directa de descarga y snippets de código.

**Pasos:**
1. `GET /api/v1/download/<repo>/resolve?filename=model.safetensors`.
2. `HFDownloadManager.resolve_url()` construye URL + curl command.
3. `GET /api/v1/download/<repo>/files` lista archivos del repo.
4. `GET /api/v1/download/<repo>/snippets` genera snippets (transformers, diffusers, datasets, hub).

**Evidencia:** `Dict` con URL, curl, snippets.

---

### 8.11 Instructivo de gestión de endpoints de inferencia (WI-320-11)

**Propósito:** Crear y gestionar Inference Endpoints de Hugging Face.

**Pasos:**
1. `POST /api/v1/endpoints` con `model_id`, `hardware`, `region` (rol `endpoints:create`).
2. `InferenceEndpointManager.create()` crea endpoint en HF con token del usuario.
3. `GET /api/v1/endpoints/<id>/health` verifica estado.
4. `POST /api/v1/endpoints/<id>/stop` detiene endpoint (rol `endpoints:stop`).
5. `DELETE /api/v1/endpoints/<id>` elimina endpoint (rol `endpoints:delete`).

**Evidencia:** Endpoint creado con `billing_account = user_hf_username`.

---

### 8.12 Instructivo de gestión de Spaces (WI-320-12)

**Propósito:** Crear y gestionar Hugging Face Spaces.

**Pasos:**
1. `POST /api/v1/spaces` con `space_id`, `sdk` (gradio/streamlit) (rol `spaces:create`).
2. `SpaceManager.create()` crea Space en HF con token del usuario.
3. `GET /api/v1/spaces` lista Spaces.
4. `POST /api/v1/spaces/<id>/stop` detiene Space (rol `spaces:stop`).
5. `DELETE /api/v1/spaces/<id>` elimina Space (rol `spaces:delete`).

**Evidencia:** Space creado con URL pública.

---

### 8.13 Instructivo de auditoría y revisión (WI-320-13)

**Propósito:** Revisar el audit log de operaciones sensibles.

**Pasos:**
1. `GET /api/v1/audit` (rol `catalog:browse`).
2. Filtrar por `trace_id`, `user`, `model`, `operation`, `date_range`.
3. Verificar que cada operación tiene gates PRE/EXEC/POST registrados.
4. Verificar billing metadata: `user_hf_username` presente.
5. En caso de anomalía, escalar a admin y revisar sesiones activas.

**Evidencia:** Audit log con trazabilidad completa.

---

### 8.14 Instructivo de gestión de allowlist de modelos (WI-320-14)

**Propósito:** Aprobar o rechazar modelos para uso en UTRON.ai.

**Pasos:**
1. Revisar `ModelCatalog.list_models()` para ver modelos aprobados.
2. Para aprobar nuevo modelo: `ModelCatalog.register(entry)`.
3. Verificar: licencia, task, cost, latency, commercial_use.
4. `HuggingFaceModelGateway` rechaza cualquier modelo no en allowlist.
5. `UC324GateIntegrator.gate_pre()` valida allowlist en cada inferencia.

**Evidencia:** `ModelEntry` registrado en `ModelCatalog`.

---

### 8.15 Instructivo de operación en producción (WI-320-15)

**Propósito:** Operar UC-320 en modo producción con backends reales.

**Pasos:**
1. Configurar `UC320_BACKEND=huggingface` en `.env.production`.
2. Configurar `HF_OAUTH_CLIENT_ID`, `HF_OAUTH_CLIENT_SECRET`, `HF_OAUTH_REDIRECT_URI`.
3. Verificar que `K8S_NAMESPACE` y `K8S_PVC_NAME` apuntan al clúster real.
4. Ejecutar `pytest tests/ -q` → debe mostrar `360 passed`.
5. Construir imagen Docker y desplegar en K8s.
6. Verificar `GET /health` → `{"status": "ok"}`.
7. Verificar `GET /api/v1/auth/status` → backend `huggingface`.
8. Probar OAuth flow end-to-end.
9. Ejecutar `verify-production.sh` para validación completa.

**Evidencia:** 20-item checklist de producción (ver UC-320.md sección 24.16).

---

## 9. API REST UC-320 — Mapa completo de endpoints

### 9.1 Autenticación y OAuth

| Método | Endpoint | Permiso | Proceso |
|---|---|---|---|
| POST | `/api/v1/auth/login` | Público | SP-320.01.2 |
| GET | `/api/v1/auth/whoami` | Autenticado | SP-320.01.2 |
| POST | `/api/v1/auth/logout` | Autenticado | SP-320.01.2 |
| GET | `/api/v1/auth/status` | Público | SP-320.07 |
| GET | `/api/v1/auth/sessions` | `admin` | SP-320.07.5 |
| GET | `/api/v1/auth/oauth/login` | Público | SP-320.01.5 |
| GET | `/api/v1/auth/oauth/callback` | Público | SP-320.01.6 |
| GET | `/api/v1/auth/oauth/scopes` | Público | SP-320.01.7 |

### 9.2 Catálogo y panel

| Método | Endpoint | Permiso | Proceso |
|---|---|---|---|
| GET | `/api/v1/catalog/models` | `catalog:browse` | SP-320.02.1 |
| GET | `/api/v1/catalog/datasets` | `catalog:browse` | SP-320.02.2 |
| GET | `/api/v1/catalog/spaces` | `catalog:browse` | SP-320.02.3 |
| GET | `/api/v1/catalog/search` | `catalog:browse` | SP-320.02.6 |
| GET | `/api/v1/catalog/models/<id>` | `catalog:browse` | SP-320.02.4 |
| GET | `/api/v1/catalog/models/<id>/gated` | `catalog:browse` | SP-320.02.5 |
| GET | `/api/v1/panel/<model_id>` | `catalog:browse` | SP-320.02.13 |
| GET | `/api/v1/panel/<model_id>/vram` | `catalog:browse` | SP-320.02.7 |
| POST | `/api/v1/panel/<model_id>/vram/estimate` | `catalog:browse` | SP-320.02.7 |
| GET | `/api/v1/panel/<model_id>/playground` | `catalog:browse` | SP-320.02.12 |
| GET | `/api/v1/panel/<model_id>/license` | `catalog:browse` | SP-320.02.8 |
| GET | `/api/v1/panel/<model_id>/k8s-manifest` | `catalog:browse` | SP-320.02.9 |
| GET | `/api/v1/panel/<model_id>/benchmarks` | `catalog:browse` | SP-320.02.10 |
| POST | `/api/v1/panel/benchmarks/compare` | `catalog:browse` | SP-320.02.10 |
| GET | `/api/v1/panel/<model_id>/lineage` | `catalog:browse` | SP-320.02.11 |
| POST | `/api/v1/panel/<model_id>/lineage/register` | `models:push` | SP-320.06.5 |
| GET | `/api/v1/panel/<model_id>/training-history` | `catalog:browse` | SP-320.06.7 |

### 9.3 Inferencia

| Método | Endpoint | Permiso | Proceso |
|---|---|---|---|
| POST | `/api/v1/sentiment` | `inference:read` | SP-320.03.4 |
| POST | `/api/v1/embedding` | `inference:read` | SP-320.03.5 |
| POST | `/api/v1/classify` | `inference:read` | SP-320.03.6 |
| POST | `/api/v1/benchmark` | `benchmark:run` | SP-320.04.15 |

### 9.4 Entrenamiento, PEFT y evaluación

| Método | Endpoint | Permiso | Proceso |
|---|---|---|---|
| POST | `/api/v1/training/submit` | `models:train` | SP-320.04.1 |
| POST | `/api/v1/training/run` | `models:train` | SP-320.04.2 |
| POST | `/api/v1/training/promote` | `training:promote` | SP-320.04.3 |
| GET | `/api/v1/training/jobs` | `models:train` | SP-320.04.1 |
| POST | `/api/v1/finetune/generate` | `models:adapt` | SP-320.04.4 |
| POST | `/api/v1/trainer/train` | `models:train` | SP-320.04.10 |
| GET | `/api/v1/trainer/jobs` | `models:train` | SP-320.04.10 |
| GET | `/api/v1/peft/adapters` | `models:adapt` | SP-320.04.11 |
| POST | `/api/v1/peft/adapters` | `models:adapt` | SP-320.04.11 |
| POST | `/api/v1/peft/adapters/<id>/save` | `models:push` | SP-320.04.12 |
| POST | `/api/v1/evaluate/compute` | `evaluate:compute` | SP-320.04.13 |
| POST | `/api/v1/evaluate/compare` | `evaluate:compute` | SP-320.04.14 |
| GET | `/api/v1/evaluate/results` | `evaluate:compute` | SP-320.04.13 |

### 9.5 Servicios HF (Endpoints, Datasets, Spaces, Model Cards)

| Método | Endpoint | Permiso | Proceso |
|---|---|---|---|
| GET | `/api/v1/endpoints` | `catalog:browse` | SP-320.02.1 |
| POST | `/api/v1/endpoints` | `endpoints:create` | WI-320-11 |
| GET | `/api/v1/endpoints/<id>/health` | `endpoints:health` | WI-320-11 |
| POST | `/api/v1/endpoints/<id>/stop` | `endpoints:stop` | WI-320-11 |
| DELETE | `/api/v1/endpoints/<id>` | `endpoints:delete` | WI-320-11 |
| GET | `/api/v1/datasets` | `datasets:read` | SP-320.04.7 |
| POST | `/api/v1/datasets/load` | `datasets:load` | SP-320.04.7 |
| POST | `/api/v1/datasets/validate` | `datasets:read` | SP-320.04.8 |
| POST | `/api/v1/datasets/transform` | `datasets:transform` | SP-320.04.9 |
| GET | `/api/v1/spaces` | `spaces:read` | WI-320-12 |
| POST | `/api/v1/spaces` | `spaces:create` | WI-320-12 |
| POST | `/api/v1/spaces/<id>/stop` | `spaces:stop` | WI-320-12 |
| DELETE | `/api/v1/spaces/<id>` | `spaces:delete` | WI-320-12 |
| GET | `/api/v1/model-cards` | `model_cards:read` | SP-320.06.1 |
| POST | `/api/v1/model-cards` | `model_cards:create` | SP-320.06.1 |
| GET | `/api/v1/model-cards/<id>` | `model_cards:read` | SP-320.06.1 |
| GET | `/api/v1/model-cards/<id>/markdown` | `model_cards:read` | SP-320.06.4 |
| POST | `/api/v1/model-cards/<id>/approve` | `model_cards:approve` | SP-320.06.2 |
| POST | `/api/v1/model-cards/<id>/push` | `model_cards:push` | SP-320.06.3 |

### 9.6 Descargas

| Método | Endpoint | Permiso | Proceso |
|---|---|---|---|
| GET | `/api/v1/download/<repo>/resolve` | `models:download` | SP-320.02.14 |
| GET | `/api/v1/download/<repo>/files` | `models:download` | SP-320.02.14 |
| GET | `/api/v1/download/<repo>/info` | `models:download` | SP-320.02.14 |
| GET | `/api/v1/download/<repo>/snippets` | `models:download` | SP-320.02.15 |

### 9.7 Pipeline K8s

| Método | Endpoint | Permiso | Proceso |
|---|---|---|---|
| POST | `/api/v1/pipeline/execute` | `models:train` | SP-320.05.7 |
| GET | `/api/v1/pipeline/pkce` | `catalog:browse` | SP-320.05.1.1 |
| POST | `/api/v1/pipeline/jwt/validate` | `catalog:browse` | SP-320.05.1.2 |
| GET | `/api/v1/pipeline/secrets` | `catalog:browse` | SP-320.05.1.3 |
| POST | `/api/v1/pipeline/secrets` | `models:train` | SP-320.05.1.3 |
| DELETE | `/api/v1/pipeline/secrets/<name>` | `models:train` | SP-320.05.1.4 |
| POST | `/api/v1/pipeline/preflight` | `catalog:browse` | SP-320.05.2.4 |
| GET | `/api/v1/pipeline/cluster/nodes` | `catalog:browse` | SP-320.05.2.3 |
| POST | `/api/v1/pipeline/manifest/vllm` | `catalog:browse` | SP-320.05.3.1 |
| POST | `/api/v1/pipeline/manifest/pytorchjob` | `models:train` | SP-320.05.3.2 |
| POST | `/api/v1/pipeline/manifest/rayjob` | `models:train` | SP-320.05.3.3 |
| GET | `/api/v1/pipeline/manifest/pvc` | `catalog:browse` | SP-320.05.3.4 |
| POST | `/api/v1/pipeline/apply` | `models:train` | SP-320.05.3.5 |
| POST | `/api/v1/pipeline/cache/check` | `catalog:browse` | SP-320.05.4.1 |
| GET | `/api/v1/pipeline/cache` | `catalog:browse` | SP-320.05.4.3 |
| POST | `/api/v1/pipeline/cache/prefetch` | `models:download` | SP-320.05.4.2 |
| GET | `/api/v1/pipeline/jobs` | `catalog:browse` | SP-320.05.5.4 |
| GET | `/api/v1/pipeline/jobs/<name>/metrics` | `catalog:browse` | SP-320.05.5.4 |
| POST | `/api/v1/pipeline/jobs/<name>/metrics/subscribe` | `catalog:browse` | SP-320.05.5.3 |
| POST | `/api/v1/pipeline/package` | `models:adapt` | SP-320.05.6.1 |
| POST | `/api/v1/pipeline/publish` | `models:push` | SP-320.05.6.2 |
| POST | `/api/v1/pipeline/cleanup` | `models:train` | SP-320.05.6.3 |

### 9.8 Auditoría

| Método | Endpoint | Permiso | Proceso |
|---|---|---|---|
| GET | `/api/v1/audit` | `catalog:browse` | SP-320.07.4 |
| GET | `/api/v1/hf/status` | Autenticado | SP-320.07 |
| GET | `/api/v1/schema` | Público | Documentación |
| GET | `/health` | Público | Liveness |

---

## 10. Matriz de trazabilidad requisitos ↔ procesos

| Requisito UC-320.md | Procesos involucrados | Evidencia |
|---|---|---|
| Autenticación con HF Token | MP-320.01 | `HFAuth.authenticate()` |
| OAuth 2.0 + PKCE | MP-320.01 | `HFOAuth.exchange_code()`, `PKCEVerifier` |
| Roles y permisos | MP-320.01 | `require_permission()` decorator |
| Catálogo de modelos/datasets/spaces | MP-320.02 | `HFCatalogBrowser.list_*()` |
| Panel de decisión (VRAM, license, K8s, benchmarks) | MP-320.02 | `ModelPanel.get_model_card_panel()` |
| Inferencia con gates UC-324 | MP-320.03 | `UC324GateIntegrator.gate_pre/exec/post()` |
| Generación de evidencia (no orden) | MP-320.03 | `MarketSentimentSkill.run()` |
| Entrenamiento con aprobación humana | MP-320.04 | `TrainingManager.promote()` |
| Scripts LoRA/QLoRA | MP-320.04 | `ScriptGenerator.generate_lora_script()` |
| PEFT adapters | MP-320.04 | `PEFTService.create_adapter()` |
| Evaluación de métricas | MP-320.04 | `EvaluateService.compute()` |
| Pipeline K8s Paso 1 (PKCE + JWT + Secret) | MP-320.05 | `PKCEVerifier`, `JWTValidator`, `SecretManager` |
| Pipeline K8s Paso 2 (Pre-flight) | MP-320.05 | `K8sClusterValidator.pre_flight_check()` |
| Pipeline K8s Paso 3 (Manifest + apply) | MP-320.05 | `K8sManifestBuilder`, `K8sAPIClient` |
| Pipeline K8s Paso 4 (PVC + cache SHA-256) | MP-320.05 | `SharedCacheManager.check_cache()` |
| Pipeline K8s Paso 5 (Métricas WebSocket) | MP-320.05 | `MetricsStreamer.simulate_training_metrics()` |
| Pipeline K8s Paso 6 (Publish + GC) | MP-320.05 | `HubPublisher.upload_folder()`, `GarbageCollector` |
| Model cards con aprobación | MP-320.06 | `ModelCardService.approve()` |
| Linaje de modelos | MP-320.06 | `LineageTracker.register_derivation()` |
| Auditoría y billing | MP-320.07 | `/api/v1/audit`, billing metadata |
| Descargas directas y snippets | MP-320.02 | `HFDownloadManager.resolve_url()` |
| Endpoints de inferencia HF | MP-320.02 | `InferenceEndpointManager.create()` |
| Spaces de HF | MP-320.02 | `SpaceManager.create()` |
| Allowlist de modelos | MP-320.03 | `ModelCatalog.is_allowed()` |
| Facturación a cuenta del usuario | MP-320.07 | `billing_account = user_hf_username` |

---

## 11. Referencias UC-320

- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/UC-320.md" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/UC-320.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/api_320.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/orchestrator.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/contracts.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/uc324_gates.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/skills.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_gateway.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_auth.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_oauth.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_services.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_catalog.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_download.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_script_generator.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_model_panel.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/hf_k8s_pipeline.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/training.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/benchmark.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/model_catalog.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/templates.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/tests/test_api.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/tests/test_auth.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/tests/test_hf_services.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/tests/test_catalog.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/tests/test_model_panel.py" />
- <ref_file file="/Users/utron/Documents/code-books/TomoIII/UC-320/code/tests/test_k8s_pipeline.py" />
