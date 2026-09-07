## Cómo las mejoras de UC-322 afectan al cerebro AGI

Tu decisión de copiar UC-315 dentro de UC-322 tiene sentido porque UC-322 **no modifica** los archivos originales de UC-315. En cambio, UC-322 **envuelve y reemplaza funciones específicas** del cerebro. Los archivos originales siguen intactos. Veamos exactamente qué cambia:

### 1. Juice binario → Negociación con concesiones

**Archivo afectado:** `juice_agents.py`, método `_local_validate()` (líneas 160-183)

```
ANTES (UC-315):
  consensus = mean(agent_scores)
  approved = consensus >= 0.55 and not all_issues  ← binario: sí/no

DESPUÉS (UC-322):
  NegotiationEngine.negotiate() ejecuta hasta 5 rondas de concesiones
  Cada agente cede proporcionalmente a: flexibilidad × reputación_del_otro × ronda
  Si gap < threshold → acuerdo con matices (no binario)
```

**Impacto en el cerebro:** El cerebro ya no pierde información cuando dos agentes discrepan. Antes, si `consensus < 0.55` se bloqueaba todo. Ahora se negocia y se preserva el contexto de por qué cada agente tiene su posición. El cerebro recibe una resolución graduada, no un sí/no.

### 2. Voto estático → Voto dinámico por reputación

**Archivo afectado:** `trading_agents.py`, método `TraderAgent.generate_signal()` (líneas 163-187)

```
ANTES (UC-315):
  weights = {"technical": 0.35, "sentiment": 0.25, "fundamental": 0.15}  ← fijo siempre

DESPUÉS (UC-322):
  peso = ReputationSystem.get_reputation(agent_id, domain) × confidence
  Un agente con rep=0.95 tiene 2× el peso de uno con rep=0.50
```

**Impacto en el cerebro:** El cerebro **aprende** de la historia. Si el TechnicalAnalyst acierta 8 de 10 veces en trading, su voto pesa más. Si el SentimentAnalyst falla consistentemente, su influencia baja automáticamente. Los pesos fijos `0.35/0.25/0.15` ya no determinan quién gana; lo determina el historial real.

### 3. CNP estático → CNP con reputación dinámica

**Archivo afectado:** `cnp_broadcast_middleware.py`, campo `CNPAgentProfile.reliability` (línea 33) y `score()` (líneas 195-201)

```
ANTES (UC-315):
  reliability = 0.9  ← fijo, nunca cambia
  score = 0.5×bid + 0.3×conf - 0.1×cost - 0.1×latency

DESPUÉS (UC-322):
  reputation = f(success_rate, avg_quality, avg_efficiency, recent_failures)  ← se actualiza
  score = 0.35×bid + 0.25×conf + 0.25×reputation - 0.10×cost - 0.05×latency
```

**Impacto en el cerebro:** La `reliability = 0.9` estática significaba que todos los agentes eran igualmente confiables para siempre. Ahora el cerebro puede **degradar** a un agente que falla repetidamente y **promover** a uno que demuestra calidad. El CNP ya no asigna tareas a agentes que históricamente fallan.

### 4. MetacognitiveMonitor implícito → Escalación formal

**Archivo afectado:** `metacognitive_monitor.py`, método `_map_verdict()` (líneas 113-121)

```
ANTES (UC-315):
  if meta.get("abort") → "STOP"
  if meta.get("need_review") → "REVIEW"
  else → "PROCEED"
  (3 veredictos, sin circuit breaker, sin conteo de conflictos)

DESPUÉS (UC-322):
  4 veredictos: PROCEED | REVIEW | STOP | REASSIGN
  + categorización por severidad (LOW/HIGH/CRITICAL)
  + circuit breaker tras 3 conflictos consecutivos → STOP automático
  + REASSIGN cuando CNP encuentra un ganador mejor
```

**Impacto en el cerebro:** El `MetacognitiveMonitor` original solo tenía 3 opciones y no tenía memoria de conflictos previos. El cerebro podía entrar en un loop infinito de `REVIEW → retry → REVIEW → retry`. Con UC-322, después de 3 conflictos consecutivos el circuit breaker se abre y **detiene** el dominio, forzando intervención humana en lugar de girar en círculos.

### 5. Sin detección de duplicados → Fingerprints SHA-256

**Archivo afectado:** `global_workspace.py`, método `broadcast()` (líneas 52-82)

```
ANTES (UC-315):
  broadcast() publica la hipótesis ganadora y la persiste
  NO verifica si dos agentes están haciendo la misma tarea
  → Agente A y Agente B podrían ambos ejecutar "Comprar 100 AAPL"

DESPUÉS (UC-322):
  DuplicateDetection.register_task(task_id, agent_id, domain, description)
  Fingerprint = SHA-256(normalize(description))
  Si fingerprint ya existe con otro agent_id → conflicto detectado
```

**Impacto en el cerebro:** Sin esta protección, el cerebro podía ejecutar la misma orden de trading dos veces (uno vía TechnicalAnalyst, otro vía SentimentAnalyst). UC-322 detecta que ambas tareas son "Comprar AAPL" y resuelve cuál agente la ejecuta.

### 6. Sin detección de deadlocks → DFS en grafo de espera

```
ANTES (UC-315):
  Si Agente A espera resultado de Agente B, y B espera a A → colgado indefinidamente

DESPUÉS (UC-322):
  DeadlockDetector.add_dependency(A, B)
  DeadlockDetector.detect_cycle() → DFS encuentra ciclo [A→B→A]
  → Circuit breaker rompe el ciclo
```

**Impacto en el cerebro:** El cerebro ya no se puede colgar por dependencias circulares entre agentes. Antes, un deadlock silencioso podía detener todo el pipeline de trading sin que nadie supiera por qué.

### 7. Sin circuit breaker → Protección automática

```
ANTES (UC-315):
  Un agente que falla repetidamente sigue intentando indefinidamente
  No hay límite de reintentos
  No hay detención automática

DESPUÉS (UC-322):
  Conflicto no resuelto #1 → contador++
  Conflicto no resuelto #2 → contador++
  Conflicto no resuelto #3 → CIRCUIT BREAKER ABIERTO → dominio detenido
  → Alerta Prometheus: CircuitBreakerAbierto (critical)
  → Requiere reset manual: POST /api/v1/escalation/circuit-breaker/reset
```

**Impacto en el cerebro:** El cerebro gana **autoprotección**. Sin circuit breaker, un error en datos de mercado podía causar que los agentes discreparan infinitamente, consumiendo recursos sin producir resultados. Ahora el sistema se detiene y pide ayuda.

---

### Resumen: ¿Se modificaron los archivos de UC-315?

**No.** Los archivos copiados de UC-315 (`juice_agents.py`, `trading_agents.py`, `cnp_broadcast_middleware.py`, `metacognitive_monitor.py`, `global_workspace.py`) **no fueron modificados**. UC-322 los **envuelve** con una capa superior:

```
                      Antes (UC-315 solo)                 Ahora (UC-315 + UC-322)
                    ┌──────────────────┐               ┌──────────────────────────┐
                    │  Juice: sí/no    │               │  UC-322 NegotiationEngine │
                    │  Voto: fijo      │     →         │  envuelve y reemplaza     │
                    │  CNP: estático   │               │  las funciones de decisión│
                    │  Monitor: 3 opc  │               │  sin tocar el código base │
                    │  Sin protección  │               │  + duplicados + deadlocks │
                    └──────────────────┘               │  + circuit breaker        │
                                                       └──────────────────────────┘
```

El cerebro sigue funcionando igual internamente. UC-322 actúa como **middleware** entre las propuestas de los agentes y la decisión final, interceptando los conflictos antes de que lleguen a ejecución.