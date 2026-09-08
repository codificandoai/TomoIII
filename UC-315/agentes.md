## Clasificación de agentes del ecosistema UTRON.ai/TomoIII
### Agentes Reactivos (responden directamente, sin planificación compleja)

| UC | Componente | Por qué es reactivo |
|----|-----------|---------------------|
| **UC-324** | Contención, autorización, auditoría, rollback | Actúa como un "cortacircuitos": bloquea acciones inseguras **inmediatamente** cuando detecta una violación. No planifica — reacciona. Es el termostato del ecosistema: si la temperatura (peligro) sube, corta. |
| **UC-087** | DevSecOps/MLSecOps (integridad criptográfica) | Valida hash, firma, outliers, adversariales. Su lógica es **estímulo-respuesta**: dato entra → check criptográfico → approve/quarantine/rollback. No hay planificación futura, solo verificación de reglas. |
| **UC-317** | Ejecutor (mencionado en el boundary) | "UC-315 decide, UC-317 ejecuta". Recibe una orden y la ejecuta. Sin memoria propia ni planificación — es el actuador puro. |

### Agentes Deliberativos (planifican con modelos del mundo)

| UC | Componente | Por qué es deliberativo |
|----|-----------|------------------------|
| **UC-329 / GraphRAG-GoT** | Graph reasoning, contradicción, caminos alternativos | Simula múltiples caminos de razonamiento (Graph of Thoughts), explora alternativas, detecta contradicciones. Como el ajedrecista: evalúa movimientos futuros antes de elegir. |
| **UC-325** | Auto-reflexión y control de calidad del razonamiento | Razona **sobre el razonamiento**. Evalúa la calidad de las inferencias antes de emitirlas. Necesita un modelo del mundo para juzgar si una conclusión es válida. |
| **UC-307** | Plasticidad sináptica digital y evolución cognitiva | Planifica la evolución del sistema a largo plazo. Decide qué conexiones conceptuales fortalecer o debilitar basándose en modelos de utilidad futura. |

### Agentes Híbridos (reactivos + deliberativos)

| UC | Componente | Por qué es híbrido |
|----|-----------|---------------------|
| **UC-326 / MAQRI** | Memoria persistente + retrieval inteligente | **Reactivo**: responde a queries de recuperación inmediatamente. **Deliberativo**: decide estratégicamente qué memorias consolidar, qué olvidar, cómo indexar para optimizar retrieval futuro. |
| **UC-328 / ORQUESTA-R** | Orquestación RAG resiliente | **Reactivo**: sirve respuestas RAG en tiempo real. **Deliberativo**: planifica estrategias de resiliencia, failover, degradación graceful ante caídas de componentes. |
| **UC-330** | Governance exploración-explotación | **Reactivo**: aplica políticas hard gates inmediatamente. **Deliberativo**: balancea exploración (probar nuevas estrategias) vs explotación (usar lo conocido) con Q-learning y contextual bandits a largo plazo. |
| **UC-083** | TrackPrice.ai incident response + self-healing | **Reactivo**: detecta y mitiga incidentes en tiempo real (como un pager automático). **Deliberativo**: diagnostica causa raíz, planifica mitigación, ajusta batch inference para resiliencia futura. |
| **UC-162** | LLMOps governance (sesgo, linaje, hallucination, drift) | **Reactivo**: verifica sesgo, hallucination y estructura en cada lote/respuesta — checks inmediatos. **Deliberativo**: evalúa drift conceptual a lo largo del tiempo, mantiene linaje semántico como modelo del mundo de transformaciones, versiona prompts con evaluación estratégica. |
| **UC-296** | Gestión de memoria | **Reactivo**: sirve y almacena memorias on-demand. **Deliberativo**: decide políticas de retención, consolidación y poda basándose en modelos de relevancia futura. |

### Agentes BDI (Creencia, Deseo, Intención)

| UC | Componente | Por qué es BDI |
|----|-----------|----------------|
| **UC-315** | Cerebro AGI canónico — autoridad final de decisión | **Creencia**: mantiene modelos del mundo continuamente actualizados (validados por UC-087 y UC-162). **Deseo**: tiene metas del sistema (objetivos del ecosistema). **Intención**: se compromete a acciones concretas y delega ejecución a UC-317. Es el agente BDI por excelencia: *cree* que el conocimiento es válido (porque UC-087 + UC-162 lo aprobaron), *desea* lograr el objetivo, e *intenta* ejecutar la acción óptima. |
| **UC-322** | Resolución de conflictos entre agentes | **Creencia**: mantiene creencias sobre el estado de cada agente y sus afirmaciones. **Deseo**: armonizar el ecosistema (meta de coherencia). **Intención**: se compromete a un curso de resolución (mediación, priorización, arbitraje). Como el asistente que *cree* que un vuelo está retrasado, *desea* llevar al pasajero a destino, e *intenta* reservar otro vuelo — UC-322 *cree* que dos agentes entran en conflicto, *desea* resolverlo, e *intenta* mediar. |

---

## Mapa visual del ecosistema por tipo

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ECOSISTEMA UTRON.ai / TomoIII                     │
│                                                                     │
│  BDI (Creencia-Deseo-Intención)                                     │
│  ┌──────────────────┐  ┌──────────────────┐                        │
│  │   UC-315         │  │   UC-322         │                        │
│  │   (AGI brain)    │  │   (Conflict      │                        │
│  │   decide         │  │    resolution)   │                        │
│  └────────┬─────────┘  └──────────────────┘                        │
│           │                                                         │
│           ▼ delega ejecución                                        │
│  ┌──────────────────┐                                               │
│  │   UC-317         │  REACTIVO                                     │
│  │   (Ejecutor)     │  (actuador puro)                              │
│  └──────────────────┘                                               │
│                                                                     │
│  DELIBERATIVOS (planifican con modelos del mundo)                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  UC-329          │  │  UC-325          │  │  UC-307          │  │
│  │  (GraphRAG-GoT)  │  │  (Self-reflection)│  │  (Plasticidad)   │  │
│  │  caminos futuros │  │  meta-razonamiento│  │  evolución cogn. │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                     │
│  HÍBRIDOS (reactivo + deliberativo)                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ UC-326   │ │ UC-328   │ │ UC-330   │ │ UC-083   │ │ UC-162   │ │
│  │ (MAQRI)  │ │(ORQUESTA)│ │(Expl/Exp)│ │(TrackPrc)│ │ (LLMOps) │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│  ┌──────────┐                                                       │
│  │ UC-296   │                                                       │
│  │(Memoria) │                                                       │
│  └──────────┘                                                       │
│                                                                     │
│  REACTIVOS (estímulo-respuesta, sin planificación)                  │
│  ┌──────────────────┐  ┌──────────────────┐                        │
│  │   UC-324         │  │   UC-087         │                        │
│  │   (Contención)   │  │   (MLSecOps)     │                        │
│  │   bloquea ya     │  │   valida ya      │                        │
│  └──────────────────┘  └──────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Justificación del patrón arquitectónico

La distribución no es accidental — refleja el principio de autoridad del ecosistema:

> **UC-315 decide, UC-317 ejecuta, UC-324 contiene, UC-322 resuelve conflictos.**

- **UC-315 es BDI** porque necesita mantener creencias actualizadas sobre el mundo (modelos validados), tener deseos (metas del sistema) y comprometerse con intenciones (planes de acción). Es el único componente que puede "decidir".

- **UC-324 y UC-087 son reactivos** porque **no deben planificar** — deben bloquear **inmediatamente**. Si un agente de contención deliberara, sería demasiado lento para detener una acción peligrosa. Su valor está en la velocidad de reacción, no en la profundidad de razonamiento.

- **UC-329, UC-325, UC-307 son deliberativos** porque su valor está en la **profundidad**: explorar caminos alternativos, reflexionar sobre la calidad del razonamiento, planificar la evolución cognitiva. No necesitan reaccionar instantáneamente.

- **UC-326, UC-328, UC-330, UC-083, UC-162, UC-296 son híbridos** porque operan en dos tiempos: responden a eventos en tiempo real (reactivo) **y** optimizan estrategias a largo plazo (deliberativo). Esta dualidad es esencial para sistemas del mundo real.

- **UC-322 es BDI** porque la resolución de conflictos requiere entender las **creencias** de cada agente en disputa, **desear** la armonía del sistema, y **comprometerse** con una decisión de mediación que todos deben acatar.

> **Principio clave**: Un modelo genera evidencia. La evidencia no es una orden. Los agentes reactivos (UC-324, UC-087) garantizan que ninguna evidencia se convierta en orden sin validación. Los agentes BDI (UC-315, UC-322) garantizan que las decisiones sean coherentes con creencias validadas. Los híbridos y deliberativos proporcionan la profundidad de razonamiento que alimenta esas creencias.