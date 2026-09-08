"""
UC-308 — Exports públicos del módulo Agent Drift / Environmental Degradation.
"""

from __future__ import annotations

from alert_manager_308 import AlertManager
from baseline_manager import BaselineManager
from drift_detectors import (
    APIContractDriftDetector,
    BehavioralDriftDetector,
    ConceptDriftDetector,
    DataDistributionDriftDetector,
    HTMLInterfaceDriftDetector,
    QualityDriftDetector,
    ToolOperationalDriftDetector,
)
from prediction_drift_monitor import (
    PredictionDriftMonitor,
    PredictionWindow,
)
from drift_orchestrator import DriftOrchestrator
from environment_simulator import SimulatedExternalEnvironment
from golden_dataset import (
    build_default_golden_dataset,
    get_public_cases,
    get_secret_cases,
    load_golden_dataset_from_dict,
)
from mitigation_advisor import MitigationAdvisor
from models_308 import (
    AgentResult,
    Alert,
    Baseline,
    BaselineMetrics,
    DatasetSignature,
    DriftConfig,
    DriftSignal,
    DriftStatus,
    DriftType,
    EvaluationRun,
    GoldenCase,
    GoldenDataset,
    Recommendation,
    RecommendationAction,
    SystemStatus,
)
from cc_models_308 import (
    AuditNode,
    ExperimentConfig,
    ExperimentState,
    MarketEvent,
    ModelRegistration,
    OrderSide,
    OrderState,
    PaperFill,
    PaperOrder,
    PortfolioSnapshot,
    Prediction,
    PromotionAction,
    PromotionRecommendation,
    StageMetrics,
)
from champion_challenger_experiment_308 import (
    AuthorityGuardAdapter,
    ChampionChallengerExperiment,
    ChampionChallengerManager,
    DefaultAuthorityGuard,
    DefaultHITL,
    DefaultShutdown,
    HITLApprovalAdapter,
    PaperExecutionAdapter,
    ShutdownAdapter,
    generate_market_events,
)
from cc_predictors_308 import (
    ChampionDemoPredictor,
    ChallengerDemoPredictor,
    PredictorAdapter,
    UC315SkillPredictorAdapter,
    make_demo_predictors,
)
from cc_execution_308 import PaperExecutionEngine
from cc_metrics_308 import PromotionCriteria, StageMetricsCalculator, latest_stage_metrics
from cc_audit_308 import AuditChain
from monitoring_generator_308 import (
    generate_alert_rules_yaml,
    generate_alertmanager_yaml,
    generate_grafana_dashboard,
    generate_prometheus_yaml,
)
from nightly_scheduler import CronExpressionError, NightlyScheduler
from observability_308 import ObservabilityManager
from regression_runner import RegressionRunner

__all__ = [
    "AlertManager",
    "Alert",
    "BaselineManager",
    "Baseline",
    "BaselineMetrics",
    "DatasetSignature",
    "DriftConfig",
    "DriftOrchestrator",
    "DriftSignal",
    "DriftStatus",
    "DriftType",
    "EvaluationRun",
    "GoldenCase",
    "GoldenDataset",
    "GoldenDataset",
    "Recommendation",
    "RecommendationAction",
    "SystemStatus",
    "AgentResult",
    "APIContractDriftDetector",
    "BehavioralDriftDetector",
    "ConceptDriftDetector",
    "DataDistributionDriftDetector",
    "HTMLInterfaceDriftDetector",
    "PredictionDriftMonitor",
    "PredictionWindow",
    "QualityDriftDetector",
    "ToolOperationalDriftDetector",
    "MitigationAdvisor",
    "ObservabilityManager",
    "RegressionRunner",
    "SimulatedExternalEnvironment",
    "NightlyScheduler",
    "CronExpressionError",
    "build_default_golden_dataset",
    "load_golden_dataset_from_dict",
    "get_public_cases",
    "get_secret_cases",
    "generate_prometheus_yaml",
    "generate_alert_rules_yaml",
    "generate_alertmanager_yaml",
    "generate_grafana_dashboard",
    # Champion/Challenger experiment exports
    "AuditNode",
    "AuditChain",
    "ExperimentConfig",
    "ExperimentState",
    "MarketEvent",
    "ModelRegistration",
    "OrderSide",
    "OrderState",
    "PaperFill",
    "PaperOrder",
    "PortfolioSnapshot",
    "Prediction",
    "PromotionAction",
    "PromotionRecommendation",
    "StageMetrics",
    "AuthorityGuardAdapter",
    "HITLApprovalAdapter",
    "PaperExecutionAdapter",
    "ShutdownAdapter",
    "ChampionChallengerExperiment",
    "ChampionChallengerManager",
    "DefaultAuthorityGuard",
    "DefaultHITL",
    "DefaultShutdown",
    "generate_market_events",
    "ChampionDemoPredictor",
    "ChallengerDemoPredictor",
    "PredictorAdapter",
    "UC315SkillPredictorAdapter",
    "make_demo_predictors",
    "PaperExecutionEngine",
    "PromotionCriteria",
    "StageMetricsCalculator",
    "latest_stage_metrics",
]
