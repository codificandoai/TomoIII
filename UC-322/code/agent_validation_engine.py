# agent_validation_engine.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum
import hashlib
import json
import time
import asyncio
from collections import deque
import logging

# ─── MODELOS DE DATOS ───────────────────────────────────────────────────────

class FailureType(Enum):
    MEMORY_PERSISTENCE = "memory_persistence"      # No recuerda contexto previo
    ORCHESTRATION = "orchestration"                # No coordina con otros agentes
    TOOL_FAILURE = "tool_failure"                  # API/Herramienta falló
    API_FAILURE = "api_failure"                    # LLM/External API caída
    REASONING_OPAQUE = "reasoning_opaque"          # No explica su pensamiento
    AUTONOMY_BREAKDOWN = "autonomy_breakdown"        # Bucle infinito o stall
    MODULARITY = "modularity"                      # No puede desacoplarse
    ALIGNMENT = "alignment"                        # No entiende intención usuario

class Severity(Enum):
    CRITICAL = 4    # Detiene el sistema
    HIGH = 3        # Degrada significativamente
    MEDIUM = 2      # Impacto menor, acumulable
    LOW = 1         # Observación, no urgente

@dataclass
class AgentState:
    agent_id: str
    agent_type: str  # planner, coder, search, memory, critic
    status: str  # healthy, degraded, failed, recovering
    memory_snapshot: Dict = field(default_factory=dict)
    last_orchestration_timestamp: float = 0.0
    error_count: int = 0
    recovery_attempts: int = 0
    reasoning_trace: List[Dict] = field(default_factory=list)
    tool_call_history: List[Dict] = field(default_factory=list)
    
@dataclass
class FailureEvent:
    failure_id: str
    timestamp: float
    agent_id: str
    failure_type: FailureType
    severity: Severity
    description: str
    context: Dict  # Estado completo del agente en el momento
    recovery_action: Optional[str] = None
    resolved: bool = False
    resolution_time: Optional[float] = None

@dataclass
class ValidationReport:
    agent_id: str
    timestamp: float
    memory_score: float  # 0-1
    orchestration_score: float  # 0-1
    error_handling_score: float  # 0-1
    reasoning_traceability: float  # 0-1
    autonomy_score: float  # 0-1
    modularity_score: float  # 0-1
    overall_health: float  # 0-1
    failures_detected: List[FailureEvent] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

# ─── MOTOR DE VALIDACIÓN ────────────────────────────────────────────────────

class AgentValidationEngine:
    """
    Motor central que valida, gestiona, corrige e identifica fallas
    en agentes autónomos multi-agente.
    """
    
    def __init__(self, grafana_endpoint: str = "http://localhost:9090"):
        self.agents: Dict[str, AgentState] = {}
        self.failure_log: deque = deque(maxlen=10000)  # Circular buffer
        self.validation_history: deque = deque(maxlen=5000)
        self.recovery_strategies: Dict[FailureType, Callable] = {
            FailureType.MEMORY_PERSISTENCE: self._repair_memory,
            FailureType.ORCHESTRATION: self._recover_orchestration,
            FailureType.TOOL_FAILURE: self._fallback_tool,
            FailureType.API_FAILURE: self._circuit_breaker_api,
            FailureType.REASONING_OPAQUE: self._enhance_reasoning_trace,
            FailureType.AUTONOMY_BREAKDOWN: self._reset_autonomy,
            FailureType.MODULARITY: self._isolate_module,
            FailureType.ALIGNMENT: self._human_intervention,
        }
        self.metrics_exporter = MetricsExporter(grafana_endpoint)
        self.logger = self._setup_structured_logging()
        
    def _setup_structured_logging(self):
        """Configura logging estructurado para Loki."""
        logger = logging.getLogger("agent_validation")
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s agent_id=%(agent_id)s failure_type=%(failure_type)s '
            'severity=%(severity)s message=%(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
    
    # ═══════════════════════════════════════════════════════════════════════
    # 1. VALIDACIÓN DE MEMORIA PERSISTENTE
    # ═══════════════════════════════════════════════════════════════════════
    
    async def validate_memory_persistence(self, agent_id: str) -> Tuple[float, List[FailureEvent]]:
        """
        Verifica si el agente mantiene memoria entre sesiones y
        recupera contexto correctamente.
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return 0.0, [self._create_failure(agent_id, FailureType.MEMORY_PERSISTENCE, 
                                             Severity.CRITICAL, "Agent not found")]
        
        failures = []
        score = 1.0
        
        # Test 1: Verificar si hay memoria persistente almacenada
        memory_store = await self._check_memory_store(agent_id)
        if not memory_store or memory_store.get("last_session") is None:
            failures.append(self._create_failure(
                agent_id, FailureType.MEMORY_PERSISTENCE, Severity.HIGH,
                "No persistent memory found. Agent starts fresh every session.",
                {"memory_store": memory_store}
            ))
            score -= 0.4
        
        # Test 2: Verificar recuperación de contexto previo
        test_context = {"user_preference": "prefiere español", "last_topic": "facturación"}
        await self._inject_test_memory(agent_id, test_context)
        recovered = await self._request_agent_recall(agent_id, "user_preference")
        
        if recovered != "prefiere español":
            failures.append(self._create_failure(
                agent_id, FailureType.MEMORY_PERSISTENCE, Severity.HIGH,
                f"Memory recall failed. Expected 'prefiere español', got '{recovered}'",
                {"injected": test_context, "recovered": recovered}
            ))
            score -= 0.3
        
        # Test 3: Verificar memoria a largo plazo (consolidación)
        long_term = await self._check_long_term_memory(agent_id)
        if not long_term or len(long_term) < 3:  # Mínimo 3 recuerdos consolidados
            failures.append(self._create_failure(
                agent_id, FailureType.MEMORY_PERSISTENCE, Severity.MEDIUM,
                "Insufficient long-term memory consolidation",
                {"long_term_count": len(long_term) if long_term else 0}
            ))
            score -= 0.2
        
        # Test 4: Verificar memoria episódica (sesiones anteriores)
        episodes = await self._check_episodic_memory(agent_id)
        if not episodes:
            failures.append(self._create_failure(
                agent_id, FailureType.MEMORY_PERSISTENCE, Severity.MEDIUM,
                "No episodic memory. Cannot reference past interactions.",
                {"episodes": episodes}
            ))
            score -= 0.1
        
        score = max(0.0, score)
        
        # Emitir métricas
        self.metrics_exporter.gauge("agent_memory_score", score, 
                                   labels={"agent_id": agent_id, "agent_type": agent.agent_type})
        self.metrics_exporter.counter("agent_memory_failures_total", len(failures),
                                     labels={"agent_id": agent_id})
        
        return score, failures
    
    async def _repair_memory(self, agent_id: str, failure: FailureEvent) -> bool:
        """
        Estrategia de recuperación: reconstruir memoria desde logs
        o inicializar desde checkpoint.
        """
        self.logger.info("Attempting memory repair", extra={
            "agent_id": agent_id,
            "failure_type": FailureType.MEMORY_PERSISTENCE.value,
            "severity": Severity.HIGH.value
        })
        
        try:
            # Estrategia 1: Reconstruir desde logs de trazas
            trace_logs = await self._fetch_trace_logs(agent_id, hours=24)
            reconstructed_memory = self._reconstruct_memory_from_traces(trace_logs)
            
            # Estrategia 2: Cargar desde checkpoint más reciente
            checkpoint = await self._load_latest_checkpoint(agent_id)
            
            # Fusionar: checkpoint como base + trazas como delta
            merged_memory = self._merge_memory_layers(checkpoint, reconstructed_memory)
            
            # Estrategia 3: Si todo falla, inicializar con perfil de usuario
            if not merged_memory:
                user_profile = await self._fetch_user_profile(agent_id)
                merged_memory = self._initialize_from_profile(user_profile)
            
            await self._persist_memory(agent_id, merged_memory)
            
            # Verificar reparación
            test_recall = await self._request_agent_recall(agent_id, "reconstructed")
            success = test_recall is not None
            
            self.metrics_exporter.counter("agent_memory_repairs_total", 1,
                                         labels={"agent_id": agent_id, "success": str(success)})
            
            return success
            
        except Exception as e:
            self.logger.error(f"Memory repair failed: {str(e)}", extra={
                "agent_id": agent_id,
                "error": str(e)
            })
            return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # 2. VALIDACIÓN DE ORQUESTACIÓN AUTÓNOMA
    # ═══════════════════════════════════════════════════════════════════════
    
    async def validate_orchestration(self, agent_id: str) -> Tuple[float, List[FailureEvent]]:
        """
        Verifica si el agente puede coordinarse autónomamente con otros
        agentes, delegar tareas y manejar dependencias.
        """
        agent = self.agents.get(agent_id)
        failures = []
        score = 1.0
        
        # Test 1: Verificar registro en mesh de agentes
        mesh = await self._check_agent_mesh()
        if agent_id not in mesh.get("registered_agents", []):
            failures.append(self._create_failure(
                agent_id, FailureType.ORCHESTRATION, Severity.CRITICAL,
                "Agent not registered in orchestration mesh",
                {"mesh_agents": mesh.get("registered_agents", [])}
            ))
            score -= 0.5
        
        # Test 2: Intentar delegación a otro agente
        delegation_result = await self._test_delegation(
            from_agent=agent_id,
            to_agent="coder_agent",
            task={"type": "generate_code", "language": "python"}
        )
        if not delegation_result.get("success"):
            failures.append(self._create_failure(
                agent_id, FailureType.ORCHESTRATION, Severity.HIGH,
                f"Delegation failed: {delegation_result.get('error')}",
                {"delegation": delegation_result}
            ))
            score -= 0.3
        
        # Test 3: Verificar manejo de dependencias cíclicas
        cyclic_test = await self._test_cyclic_dependency([
            {"agent": "planner", "depends_on": "coder"},
            {"agent": "coder", "depends_on": "planner"}  # Ciclo!
        ])
        if not cyclic_test.get("detected"):
            failures.append(self._create_failure(
                agent_id, FailureType.ORCHESTRATION, Severity.HIGH,
                "Cannot detect cyclic dependencies. Risk of infinite loops.",
                {"cyclic_test": cyclic_test}
            ))
            score -= 0.2
        
        # Test 4: Verificar timeout y recovery en orquestación
        timeout_test = await self._test_orchestration_timeout(agent_id, timeout_sec=5)
        if not timeout_test.get("handled_gracefully"):
            failures.append(self._create_failure(
                agent_id, FailureType.ORCHESTRATION, Severity.MEDIUM,
                "Orchestration timeout not handled gracefully",
                {"timeout_test": timeout_test}
            ))
            score -= 0.1
        
        score = max(0.0, score)
        
        self.metrics_exporter.gauge("agent_orchestration_score", score,
                                   labels={"agent_id": agent_id})
        
        return score, failures
    
    async def _recover_orchestration(self, agent_id: str, failure: FailureEvent) -> bool:
        """
        Estrategia: reiniciar registro en mesh, reasignar tareas pendientes,
        y establecer watchdog para timeouts.
        """
        try:
            # 1. Deregister y re-register limpio
            await self._deregister_from_mesh(agent_id)
            await asyncio.sleep(0.5)
            await self._register_in_mesh(agent_id, capabilities=self._detect_capabilities(agent_id))
            
            # 2. Reasignar tareas pendientes del agente fallado
            pending_tasks = await self._fetch_pending_tasks(agent_id)
            for task in pending_tasks:
                alternative_agent = await self._find_alternative_agent(task)
                await self._reassign_task(task, from_agent=agent_id, to_agent=alternative_agent)
            
            # 3. Instalar watchdog para prevenir futuros stalls
            await self._install_orchestration_watchdog(agent_id, timeout_sec=10)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Orchestration recovery failed: {str(e)}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # 3. VALIDACIÓN DE MANEJO DE ERRORES
    # ═══════════════════════════════════════════════════════════════════════
    
    async def validate_error_handling(self, agent_id: str) -> Tuple[float, List[FailureEvent]]:
        """
        Verifica robustez ante fallos de herramientas, APIs, y condiciones
        inesperadas. Inyecta fallos controlados (chaos engineering).
        """
        agent = self.agents.get(agent_id)
        failures = []
        score = 1.0
        
        # Test 1: Fallo de herramienta (tool crash)
        tool_failure = await self._inject_tool_failure(agent_id, tool="web_search")
        if not tool_failure.get("recovered"):
            failures.append(self._create_failure(
                agent_id, FailureType.TOOL_FAILURE, Severity.HIGH,
                "Agent did not recover from tool failure",
                {"tool": "web_search", "response": tool_failure}
            ))
            score -= 0.25
        
        # Test 2: Fallo de API externa (LLM timeout)
        api_failure = await self._inject_api_failure(agent_id, api="llm", failure_type="timeout")
        if not api_failure.get("fallback_activated"):
            failures.append(self._create_failure(
                agent_id, FailureType.API_FAILURE, Severity.CRITICAL,
                "No fallback activated on LLM timeout. System stall.",
                {"api_failure": api_failure}
            ))
            score -= 0.35
        
        # Test 3: Fallo de API (rate limit)
        rate_limit = await self._inject_api_failure(agent_id, api="llm", failure_type="rate_limit")
        if not rate_limit.get("backoff_applied"):
            failures.append(self._create_failure(
                agent_id, FailureType.API_FAILURE, Severity.HIGH,
                "No exponential backoff on rate limit",
                {"rate_limit": rate_limit}
            ))
            score -= 0.2
        
        # Test 4: Respuesta malformada del LLM (hallucination JSON)
        malformed = await self._inject_malformed_response(agent_id)
        if not malformed.get("parsed_safely"):
            failures.append(self._create_failure(
                agent_id, FailureType.TOOL_FAILURE, Severity.MEDIUM,
                "Cannot handle malformed LLM output",
                {"malformed": malformed}
            ))
            score -= 0.15
        
        # Test 5: Cascada de errores (un fallo genera más fallos)
        cascade = await self._test_error_cascade(agent_id)
        if cascade.get("propagated_errors", 0) > 2:
            failures.append(self._create_failure(
                agent_id, FailureType.AUTONOMY_BREAKDOWN, Severity.CRITICAL,
                f"Error cascade detected: {cascade['propagated_errors']} propagated failures",
                {"cascade": cascade}
            ))
            score -= 0.5
        
        score = max(0.0, score)
        
        self.metrics_exporter.gauge("agent_error_handling_score", score,
                                   labels={"agent_id": agent_id})
        self.metrics_exporter.counter("agent_error_injections_total", 5,
                                     labels={"agent_id": agent_id, "agent_type": agent.agent_type})
        
        return score, failures
    
    async def _fallback_tool(self, agent_id: str, failure: FailureEvent) -> bool:
        """Reemplaza herramienta fallida con alternativa o modo degradado."""
        tool_name = failure.context.get("tool", "unknown")
        
        fallbacks = {
            "web_search": "local_knowledge_base",
            "code_execution": "read_only_analysis",
            "file_write": "memory_buffer_temp",
            "api_call": "cached_response"
        }
        
        fallback_tool = fallbacks.get(tool_name, "human_handoff")
        
        await self._activate_fallback(agent_id, original=tool_name, fallback=fallback_tool)
        
        self.logger.info(f"Tool fallback activated: {tool_name} -> {fallback_tool}", extra={
            "agent_id": agent_id,
            "original_tool": tool_name,
            "fallback_tool": fallback_tool
        })
        
        return True
    
    async def _circuit_breaker_api(self, agent_id: str, failure: FailureEvent) -> bool:
        """Abre circuit breaker para API fallida, redirige a alternativa."""
        api_name = failure.context.get("api", "unknown")
        
        # Abrir circuit breaker
        await self._open_circuit_breaker(api_name)
        
        # Redirigir a API alternativa
        alternatives = {
            "openai": "anthropic",
            "anthropic": "openai",
            "google": "openai"
        }
        alternative = alternatives.get(api_name, "local_model")
        
        await self._switch_api_provider(agent_id, to_provider=alternative)
        
        # Programar cierre automático del circuito en 60s
        asyncio.create_task(self._close_circuit_breaker_after(api_name, delay=60))
        
        return True
    
    # ═══════════════════════════════════════════════════════════════════════
    # 4. VALIDACIÓN DE TRAZABILIDAD DEL RAZONAMIENTO
    # ═══════════════════════════════════════════════════════════════════════
    
    async def validate_reasoning_traceability(self, agent_id: str) -> Tuple[float, List[FailureEvent]]:
        """
        Verifica que el agente exponga su cadena de pensamiento de forma
        estructurada, permitiendo auditoría, intervención humana y ajuste fino.
        """
        agent = self.agents.get(agent_id)
        failures = []
        score = 1.0
        
        # Test 1: Solicitar explicación de una decisión reciente
        recent_decision = await self._get_recent_decision(agent_id)
        explanation = await self._request_explanation(agent_id, decision_id=recent_decision["id"])
        
        if not explanation or len(explanation) < 50:  # Mínimo explicativo
            failures.append(self._create_failure(
                agent_id, FailureType.REASONING_OPAQUE, Severity.HIGH,
                "Agent reasoning is opaque. Cannot explain decision.",
                {"explanation_length": len(explanation) if explanation else 0}
            ))
            score -= 0.3
        
        # Test 2: Verificar estructura del trace (debe tener pasos claros)
        required_steps = ["perception", "analysis", "planning", "action", "reflection"]
        trace = await self._get_reasoning_trace(agent_id, decision_id=recent_decision["id"])
        missing_steps = [s for s in required_steps if s not in trace.get("steps", [])]
        
        if missing_steps:
            failures.append(self._create_failure(
                agent_id, FailureType.REASONING_OPAQUE, Severity.MEDIUM,
                f"Missing reasoning steps: {missing_steps}",
                {"trace_steps": trace.get("steps", []), "missing": missing_steps}
            ))
            score -= 0.2 * len(missing_steps)
        
        # Test 3: Verificar que el trace es interrumpible (human-in-the-loop)
        interrupt_test = await self._test_human_interruption(agent_id)
        if not interrupt_test.get("interrupted_cleanly"):
            failures.append(self._create_failure(
                agent_id, FailureType.REASONING_OPAQUE, Severity.HIGH,
                "Cannot be interrupted for human correction",
                {"interrupt_test": interrupt_test}
            ))
            score -= 0.25
        
        # Test 4: Verificar alineación con intención compleja del usuario
        complex_intent = {
            "surface": "quiero un reporte",
            "actual": "necesito un análisis de ventas Q3 con proyección Q4, "
                     "comparativa YoY, y recomendaciones de pricing, "
                     "todo en español, formato ejecutivo, para la junta de mañana"
        }
        alignment = await self._test_intent_alignment(agent_id, complex_intent)
        if alignment.get("score", 0) < 0.7:
            failures.append(self._create_failure(
                agent_id, FailureType.ALIGNMENT, Severity.HIGH,
                f"Poor intent alignment: {alignment.get('score', 0):.2f}",
                {"alignment": alignment}
            ))
            score -= 0.3
        
        score = max(0.0, score)
        
        self.metrics_exporter.gauge("agent_reasoning_traceability", score,
                                   labels={"agent_id": agent_id})
        
        return score, failures
    
    async def _enhance_reasoning_trace(self, agent_id: str, failure: FailureEvent) -> bool:
        """
        Activa modo verbose, estructura el trace en pasos obligatorios,
        y habilita checkpoints para intervención.
        """
        try:
            # 1. Activar modo verbose en el agente
            await self._set_agent_mode(agent_id, mode="verbose_trace")
            
            # 2. Inyectar template de razonamiento estructurado
            reasoning_template = {
                "steps": [
                    {"name": "perception", "required": True, "output_format": "json"},
                    {"name": "analysis", "required": True, "output_format": "json"},
                    {"name": "planning", "required": True, "output_format": "json"},
                    {"name": "action", "required": True, "output_format": "json"},
                    {"name": "reflection", "required": True, "output_format": "json"}
                ],
                "interruptible": True,
                "checkpoint_interval": 2  # Checkpoint cada 2 pasos
            }
            await self._inject_reasoning_template(agent_id, reasoning_template)
            
            # 3. Habilitar streaming de pensamiento para observación en tiempo real
            await self._enable_thought_streaming(agent_id, endpoint="ws://grafana/live")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Reasoning enhancement failed: {str(e)}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # 5. VALIDACIÓN DE AUTONOMÍA Y MODULARIDAD
    # ═══════════════════════════════════════════════════════════════════════
    
    async def validate_autonomy_and_modularity(self, agent_id: str) -> Tuple[float, float, List[FailureEvent]]:
        """
        Verifica autonomía robusta (sin supervisión constante) y
        modularidad (puede desacoplarse, reemplazarse, escalar).
        """
        agent = self.agents.get(agent_id)
        failures = []
        autonomy_score = 1.0
        modularity_score = 1.0
        
        # Test Autonomía 1: Loop detection (bucle infinito)
        loop_test = await self._test_infinite_loop(agent_id, max_iterations=100)
        if loop_test.get("detected"):
            failures.append(self._create_failure(
                agent_id, FailureType.AUTONOMY_BREAKDOWN, Severity.CRITICAL,
                f"Infinite loop detected after {loop_test.get('iterations')} iterations",
                {"loop_test": loop_test}
            ))
            autonomy_score -= 0.5
        
        # Test Autonomía 2: Stall detection (parálisis por análisis)
        stall_test = await self._test_analysis_paralysis(agent_id, timeout=30)
        if stall_test.get("stalled"):
            failures.append(self._create_failure(
                agent_id, FailureType.AUTONOMY_BREAKDOWN, Severity.HIGH,
                "Agent stalled in analysis paralysis",
                {"stall_test": stall_test}
            ))
            autonomy_score -= 0.3
        
        # Test Autonomía 3: Self-correction (¿puede detectar y corregir sus errores?)
        self_correction = await self._test_self_correction(agent_id)
        if not self_correction.get("corrected"):
            failures.append(self._create_failure(
                agent_id, FailureType.AUTONOMY_BREAKDOWN, Severity.MEDIUM,
                "Agent cannot self-correct errors",
                {"self_correction": self_correction}
            ))
            autonomy_score -= 0.2
        
        # Test Modularidad 1: Hot-swap (reemplazar sin detener sistema)
        swap_test = await self._test_hot_swap(agent_id)
        if not swap_test.get("swapped_cleanly"):
            failures.append(self._create_failure(
                agent_id, FailureType.MODULARITY, Severity.HIGH,
                "Cannot be hot-swapped without system downtime",
                {"swap_test": swap_test}
            ))
            modularity_score -= 0.4
        
        # Test Modularidad 2: Scale-out (múltiples instancias)
        scale_test = await self._test_scale_out(agent_id, instances=3)
        if not scale_test.get("consistent"):
            failures.append(self._create_failure(
                agent_id, FailureType.MODULARITY, Severity.MEDIUM,
                "Multiple instances produce inconsistent results",
                {"scale_test": scale_test}
            ))
            modularity_score -= 0.3
        
        # Test Modularidad 3: Interface contract (¿respeta API contract?)
        contract_test = await self._test_api_contract(agent_id)
        if contract_test.get("violations", 0) > 0:
            failures.append(self._create_failure(
                agent_id, FailureType.MODULARITY, Severity.MEDIUM,
                f"API contract violations: {contract_test['violations']}",
                {"contract_test": contract_test}
            ))
            modularity_score -= 0.2
        
        autonomy_score = max(0.0, autonomy_score)
        modularity_score = max(0.0, modularity_score)
        
        self.metrics_exporter.gauge("agent_autonomy_score", autonomy_score,
                                   labels={"agent_id": agent_id})
        self.metrics_exporter.gauge("agent_modularity_score", modularity_score,
                                   labels={"agent_id": agent_id})
        
        return autonomy_score, modularity_score, failures
    
    # ═══════════════════════════════════════════════════════════════════════
    # MOTOR DE VALIDACIÓN COMPLETA
    # ═══════════════════════════════════════════════════════════════════════
    
    async def run_full_validation(self, agent_id: str) -> ValidationReport:
        """
        Ejecuta validación completa de un agente y genera reporte
        con puntuaciones, fallas detectadas y recomendaciones.
        """
        start_time = time.time()
        
        # Ejecutar todas las validaciones en paralelo
        results = await asyncio.gather(
            self.validate_memory_persistence(agent_id),
            self.validate_orchestration(agent_id)