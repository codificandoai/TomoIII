# UC_INTEROPERABILITY_MAP.md

## 1. Inventario de UCs

| UC | Responsabilidad | API Files | Tests | venv |
|---|---|---|---|---|
| UC-075 | UC-075 es una **capa externa** del ecosistema AGI que orquesta el reentrenamiento continuo de modelos desplegados en pro | api_075.py | 0 | no |
| UC-083 | ```bash | api_083.py | 0 | no |
| UC-087 | ```bash | api_087.py | 2 | no |
| UC-119 | ```bash | - | 10 | yes |
| UC-127 | ```bash | - | 6 | yes |
| UC-129 | ```bash | - | 4 | yes |
| UC-162 | ```bash | api_162.py | 0 | no |
| UC-179 | ```bash | - | 7 | yes |
| UC-251 | **Uso:** Externo / Referencia arquitectónica e implementación ejecutable. | - | 6 | no |
| UC-257 | **Uso:** Externo / Referencia arquitectónica e implementación ejecutable. | - | 4 | no |
| UC-258 | **Uso:** Externo / Referencia arquitectónica e implementación ejecutable. | - | 3 | no |
| UC-259 | --- | - | 4 | no |
| UC-260 | python UC-260.py plan --origin Madrid --destination Barcelona --departure-date 2026-09-15 --return-date 2026-09-17 --tra | - | 4 | no |
| UC-261 | --- | - | 6 | no |
| UC-262 | --- | - | 3 | no |
| UC-263 | --- | - | 4 | no |
| UC-264 | --- | - | 5 | no |
| UC-265 | --- | - | 10 | no |
| UC-266 | --- | - | 11 | no |
| UC-268 | --- | - | 3 | no |
| UC-269 | --- | - | 2 | no |
| UC-270 | ```bash | - | 5 | no |
| UC-271 | ```bash | - | 5 | no |
| UC-272 | ```bash | - | 5 | no |
| UC-273 | ```bash | - | 6 | no |
| UC-274 | ```bash | - | 6 | no |
| UC-275 | ```bash | - | 7 | no |
| UC-276 | ```bash | - | 6 | no |
| UC-277 | ```bash | - | 8 | no |
| UC-279 | UC-279 implementa un gemelo digital por SKU que conserva un estado vivo del mercado y coordina seis agentes especializad | - | 3 | yes |
| UC-280 | UC-280 convierte objetivos humanos abstractos en DAGs ejecutables, asigna tareas a agentes especializados y ejecuta en p | - | 3 | yes |
| UC-281 | UC-281 implementa un plano de control común para coordinar **LangGraph, CrewAI, Microsoft Agent Framework/AutoGen, Googl | - | 2 | yes |
| UC-283 | UC-283 implementa un sistema de autocorrección con evidencia determinista para decisiones de pricing. El generador no ev | - | 2 | no |
| UC-284 | UC-284 detalla cómo el middleware Qbex debe invocar mecanismos especializados para mitigar las limitaciones actuales de  | - | 2 | no |
| UC-289 | UC-289 ¿Qué riesgos éticos son exclusivos o cualitativamente nuevos en los agentes autónomos de IA (agentic AI) Cómo mit | - | 2 | no |
| UC-290 | ![Arquitectura](./uc-290-brain.png) | api_290.py | 0 | no |
| UC-292 | UC-292 implementa un sistema **agentic AI** para mercados financieros. Un agente asesor de trading percibe datos brutos  | - | 18 | no |
| UC-293 | UC-293 eleva el agente de trading de UC-292 de "reactivo" a **cognitivo y autocrítico**. El modelo propone planes de tra | - | 20 | no |
| UC-294 | UC-294 extiende UC-293 añadiendo una **capa de conciencia situacional funcional** inspirada en la **Global Workspace The | - | 21 | no |
| UC-295 | UC-295 añade una capa al cerebro AGI del sistema de trading multi-agente para | - | 22 | no |
| UC-296 | UC-296 añade una **capa de gestión de memoria** al cerebro AGI del sistema de | - | 24 | no |
| UC-300 | ```bash | api_300.py | 0 | no |
| UC-307 | ```bash | - | 4 | no |
| UC-308 | **Uso:** INTERNO | api_308.py | 0 | no |
| UC-309 | UC-309 responde la pregunta: **¿qué ocurrió dentro de una ejecución concreta del agente y por qué terminó así?** | api_309.py | 0 | no |
| UC-313 | UC-313 U T R O N .AI tiene una arquitectura AGI modular orientada al aprendizaje continuo, la autoobservación y la conti | - | 32 | no |
| UC-314 | **USO:** EXTERNO (API + CLI) | - | 4 | no |
| UC-315 | **USO:** INTERNO PATENTADO | - | 34 | no |
| UC-317 | ```bash | api_317.py | 4 | yes |
| UC-320 | ```bash | api_320.py | 7 | yes |
| UC-322 | **USO:** INTERNO PATENTADO | api_322.py | 0 | no |
| UC-324 | **USO:** INTERNO PATENTADO | api_324.py | 3 | yes |
| UC-325 | ```bash | api_325.py | 0 | no |
| UC-326 | ```bash | api_326.py | 0 | no |
| UC-328 | **Uso:** INTERNO PATENTE | api_328.py | 0 | no |
| UC-329 | **Uso:** INTERNO PATENTE | api_329.py | 0 | no |
| UC-330 | ```bash | api_330.py | 0 | no |
| UC-700 | "El nodo N-482 presenta riesgo elevado de fallo de memoria en las próximas 24 horas; evacuar workloads no tolerantes a f | - | 2 | no |
| UC-701 | ```bash | - | 3 | no |
| UC-702 | ```bash | - | 5 | no |
| UC-703 | **USO:** INTERNO PATENTADO | api_703.py | 15 | no |

## 2. Mapa de endpoints por UC

| UC | Método | Ruta | Contrato declarado |
|---|---|---|---|
| UC-075 | GET | `/api/v1/health` | no |
| UC-075 | GET | `/api/v1/cards` | no |
| UC-075 | POST | `/api/v1/ct/scheduled` | no |
| UC-075 | POST | `/api/v1/ct/event` | no |
| UC-075 | POST | `/api/v1/ct/on-demand` | no |
| UC-075 | POST | `/api/v1/ct/incremental` | no |
| UC-075 | POST | `/api/v1/ct/runs/<run_id>/resolve-hitl` | no |
| UC-075 | GET | `/api/v1/ct/runs` | no |
| UC-075 | GET | `/api/v1/ct/runs/<run_id>` | no |
| UC-075 | GET | `/api/v1/ct/pending-hitl` | no |
| UC-075 | GET | `/api/v1/ct/status` | no |
| UC-075 | GET | `/api/v1/ct/audit` | no |
| UC-075 | GET | `/api/v1/ct/metrics` | no |
| UC-075 | GET | `/api/v1/ct/dashboard` | no |
| UC-075 | GET | `/api/v1/ct/loki` | no |
| UC-075 | POST | `/api/v1/ct/online-fit` | no |
| UC-075 | GET | `/api/v1/ct/online-learners` | no |
| UC-075 | GET | `/api/v1/ct/online-learners/<learner_id>` | no |
| UC-075 | POST | `/api/v1/ct/regulatory/domain` | no |
| UC-075 | POST | `/api/v1/ct/regulatory/stakeholder-requirement` | no |
| UC-075 | POST | `/api/v1/ct/regulatory/sign-off` | no |
| UC-075 | POST | `/api/v1/ct/regulatory/select-model` | no |
| UC-075 | POST | `/api/v1/ct/regulatory/explainability` | no |
| UC-075 | GET | `/api/v1/ct/regulatory/requirements` | no |
| UC-075 | POST | `/api/v1/ct/global/register-artifact` | no |
| UC-075 | GET | `/api/v1/ct/global/artifacts` | no |
| UC-075 | POST | `/api/v1/ct/global/replicate` | no |
| UC-075 | POST | `/api/v1/ct/global/detect-conflicts` | no |
| UC-075 | POST | `/api/v1/ct/global/resolve-conflict` | no |
| UC-075 | POST | `/api/v1/ct/global/lifecycle/gc` | no |
| UC-075 | POST | `/api/v1/ct/global/lifecycle/legal-hold` | no |
| UC-075 | POST | `/api/v1/ct/global/dr/backup` | no |
| UC-075 | POST | `/api/v1/ct/global/dr/failover` | no |
| UC-075 | GET | `/api/v1/ct/global/dr/status` | no |
| UC-075 | GET | `/api/v1/ct/global/status` | no |
| UC-075 | POST | `/api/v1/ct/risk/register` | no |
| UC-075 | GET | `/api/v1/ct/risks` | no |
| UC-075 | GET | `/api/v1/ct/risks/<risk_id>` | no |
| UC-075 | POST | `/api/v1/ct/risks/<risk_id>/update` | no |
| UC-075 | GET | `/api/v1/ct/risks/summary` | no |
| UC-075 | GET | `/api/v1/ct/risks/proactive` | no |
| UC-075 | GET | `/api/v1/ct/risks/runbook/<category>` | no |
| UC-075 | POST | `/api/v1/ct/incident/report` | no |
| UC-075 | GET | `/api/v1/ct/incidents` | no |
| UC-075 | GET | `/api/v1/ct/incidents/<incident_id>` | no |
| UC-075 | POST | `/api/v1/ct/incidents/<incident_id>/assign` | no |
| UC-075 | POST | `/api/v1/ct/incidents/<incident_id>/resolve` | no |
| UC-075 | GET | `/api/v1/ct/incidents/summary` | no |
| UC-075 | POST | `/api/v1/ct/incidents/drill` | no |
| UC-075 | GET | `/api/v1/ct/incidents/drill/<drill_id>` | no |
| UC-075 | GET | `/api/v1/ct/incidents/learnings` | no |
| UC-075 | GET | `/api/v1/ct/incidents/playbook/<category>` | no |
| UC-075 | POST | `/api/v1/ct/adaptive/threat-intel/sync` | no |
| UC-075 | POST | `/api/v1/ct/adaptive/mine-patterns` | no |
| UC-075 | POST | `/api/v1/ct/adaptive/feedback` | no |
| UC-075 | POST | `/api/v1/ct/adaptive/playbook/pr` | no |
| UC-075 | POST | `/api/v1/ct/adaptive/playbook/merge` | no |
| UC-075 | GET | `/api/v1/ct/adaptive/playbook/history/<playbook_id>` | no |
| UC-075 | POST | `/api/v1/ct/adaptive/chaos` | no |
| UC-075 | GET | `/api/v1/ct/adaptive/chaos/<run_id>` | no |
| UC-075 | POST | `/api/v1/ct/adaptive/release-gate` | no |
| UC-075 | GET | `/api/v1/ct/adaptive/metrics` | no |
| UC-075 | POST | `/api/v1/ct/adaptive/challenge-scenario` | no |
| UC-075 | POST | `/api/v1/ct/adaptive/threat-vector` | no |
| UC-075 | POST | `/api/v1/ct/icc/incident` | no |
| UC-075 | POST | `/api/v1/ct/icc/incident/<icc_id>/status` | no |
| UC-075 | POST | `/api/v1/ct/icc/action` | no |
| UC-075 | POST | `/api/v1/ct/icc/action/<action_id>/execute` | no |
| UC-075 | POST | `/api/v1/ct/icc/action/<action_id>/rollback` | no |
| UC-075 | POST | `/api/v1/ct/icc/postmortem` | no |
| UC-075 | POST | `/api/v1/ct/icc/runbook/sync` | no |
| UC-075 | GET | `/api/v1/ct/icc/unified-view/<incident_id>` | no |
| UC-075 | GET | `/api/v1/ct/icc/status-board` | no |
| UC-083 | ROUTE | `/health` | no |
| UC-083 | ROUTE | `/` | no |
| UC-083 | ROUTE | `/api/v1/schema` | no |
| UC-083 | ROUTE | `/api/v1/incident/declare` | no |
| UC-083 | ROUTE | `/api/v1/incident/logs` | no |
| UC-083 | ROUTE | `/api/v1/incident/metrics` | no |
| UC-083 | ROUTE | `/api/v1/incident/validate` | no |
| UC-083 | ROUTE | `/api/v1/incident/triage` | no |
| UC-083 | ROUTE | `/api/v1/incident/diagnose` | no |
| UC-083 | ROUTE | `/api/v1/incident/mitigate` | no |
| UC-083 | ROUTE | `/api/v1/incident/reprocess` | no |
| UC-083 | ROUTE | `/api/v1/incident/postmortem` | no |
| UC-083 | ROUTE | `/api/v1/incident/full-response` | no |
| UC-083 | ROUTE | `/api/v1/incident/status` | no |
| UC-083 | ROUTE | `/api/v1/incident/reset` | no |
| UC-083 | ROUTE | `/metrics` | no |
| UC-087 | ROUTE | `/health` | no |
| UC-087 | ROUTE | `/` | no |
| UC-087 | ROUTE | `/api/v1/schema` | no |
| UC-087 | ROUTE | `/api/v1/validate` | no |
| UC-087 | ROUTE | `/api/v1/train-candidate` | no |
| UC-087 | ROUTE | `/api/v1/evaluate-robustness` | no |
| UC-087 | ROUTE | `/api/v1/detect-backdoors` | no |
| UC-087 | ROUTE | `/api/v1/process-batch` | no |
| UC-087 | ROUTE | `/api/v1/approve-canary` | no |
| UC-087 | ROUTE | `/api/v1/rollback` | no |
| UC-087 | ROUTE | `/api/v1/reset` | no |
| UC-087 | ROUTE | `/api/v1/status` | no |
| UC-087 | ROUTE | `/metrics` | no |
| UC-162 | ROUTE | `/health` | no |
| UC-162 | ROUTE | `/` | no |
| UC-162 | ROUTE | `/api/v1/schema` | no |
| UC-162 | ROUTE | `/api/v1/process-corpus` | no |
| UC-162 | ROUTE | `/api/v1/evaluate-response` | no |
| UC-162 | ROUTE | `/api/v1/check-drift` | no |
| UC-162 | ROUTE | `/api/v1/set-baseline` | no |
| UC-162 | ROUTE | `/api/v1/register-prompt` | no |
| UC-162 | ROUTE | `/api/v1/approve-prompt` | no |
| UC-162 | ROUTE | `/api/v1/evaluate-prompt` | no |
| UC-162 | ROUTE | `/api/v1/reset` | no |
| UC-162 | ROUTE | `/api/v1/status` | no |
| UC-162 | ROUTE | `/api/v1/prompts` | no |
| UC-162 | ROUTE | `/api/v1/lineage` | no |
| UC-162 | ROUTE | `/metrics` | no |
| UC-290 | ROUTE | `/health` | no |
| UC-290 | ROUTE | `/` | no |
| UC-290 | ROUTE | `/api/v1/schema` | no |
| UC-290 | ROUTE | `/api/v1/process-decision` | no |
| UC-290 | ROUTE | `/api/v1/submit-review` | no |
| UC-290 | ROUTE | `/api/v1/pending-reviews` | no |
| UC-290 | ROUTE | `/api/v1/dossier/<dossier_id>` | no |
| UC-290 | ROUTE | `/api/v1/present/<dossier_id>` | no |
| UC-290 | ROUTE | `/api/v1/audit-trail` | no |
| UC-290 | ROUTE | `/api/v1/status` | no |
| UC-290 | ROUTE | `/api/v1/results` | no |
| UC-290 | ROUTE | `/api/v1/reset` | no |
| UC-290 | ROUTE | `/metrics` | no |
| UC-290 | ROUTE | `/api/v1/safe-hold` | no |
| UC-290 | ROUTE | `/api/v1/safe-hold/<dossier_id>/release` | no |
| UC-300 | ROUTE | `/health` | no |
| UC-300 | ROUTE | `/` | no |
| UC-300 | ROUTE | `/api/v1/schema` | no |
| UC-300 | ROUTE | `/api/v1/authorize` | no |
| UC-300 | ROUTE | `/api/v1/execute` | no |
| UC-300 | ROUTE | `/api/v1/human-approval` | no |
| UC-300 | ROUTE | `/api/v1/status` | no |
| UC-300 | ROUTE | `/api/v1/audit-trail` | no |
| UC-300 | ROUTE | `/api/v1/metrics` | no |
| UC-300 | ROUTE | `/api/v1/reset` | no |
| UC-300 | ROUTE | `/api/v1/kill-switch` | no |
| UC-300 | ROUTE | `/api/v1/prefilter-intent` | no |
| UC-300 | ROUTE | `/api/v1/prefilter-intent/approve` | no |
| UC-300 | ROUTE | `/api/v1/intercept-proposal` | no |
| UC-300 | ROUTE | `/api/v1/intercept-proposal/approve` | no |
| UC-308 | ROUTE | `/health` | no |
| UC-308 | ROUTE | `/` | no |
| UC-308 | ROUTE | `/api/v1/schema` | no |
| UC-308 | ROUTE | `/api/v1/run-evaluation` | no |
| UC-308 | ROUTE | `/api/v1/baseline` | no |
| UC-308 | ROUTE | `/api/v1/baseline` | no |
| UC-308 | ROUTE | `/api/v1/datasets` | no |
| UC-308 | ROUTE | `/api/v1/history` | no |
| UC-308 | ROUTE | `/api/v1/alerts` | no |
| UC-308 | ROUTE | `/api/v1/alerts/acknowledge` | no |
| UC-308 | ROUTE | `/api/v1/status` | no |
| UC-308 | ROUTE | `/api/v1/metrics` | no |
| UC-308 | ROUTE | `/api/v1/reset` | no |
| UC-308 | ROUTE | `/api/v1/cc-experiments` | no |
| UC-308 | ROUTE | `/api/v1/cc-experiments` | no |
| UC-308 | ROUTE | `/api/v1/cc-experiments/<exp_id>` | no |
| UC-308 | ROUTE | `/api/v1/cc-experiments/<exp_id>/register` | no |
| UC-308 | ROUTE | `/api/v1/cc-experiments/<exp_id>/start` | no |
| UC-308 | ROUTE | `/api/v1/cc-experiments/<exp_id>/ingest` | no |
| UC-308 | ROUTE | `/api/v1/cc-experiments/<exp_id>/evaluate` | no |
| UC-308 | ROUTE | `/api/v1/cc-experiments/<exp_id>/recommend` | no |
| UC-308 | ROUTE | `/api/v1/cc-experiments/<exp_id>/approve` | no |
| UC-308 | ROUTE | `/api/v1/cc-experiments/<exp_id>/shutdown` | no |
| UC-308 | ROUTE | `/api/v1/cc-experiments/<exp_id>/generate-events` | no |
| UC-309 | ROUTE | `/health` | no |
| UC-309 | ROUTE | `/schema` | no |
| UC-309 | ROUTE | `/events` | no |
| UC-309 | ROUTE | `/batch` | no |
| UC-309 | ROUTE | `/traces` | no |
| UC-309 | ROUTE | `/traces/<trace_id>` | no |
| UC-309 | ROUTE | `/trace/<trace_id>` | no |
| UC-309 | ROUTE | `/traces/<trace_id>/validate` | no |
| UC-309 | ROUTE | `/metrics` | no |
| UC-309 | ROUTE | `/logs` | no |
| UC-309 | ROUTE | `/spans` | no |
| UC-309 | ROUTE | `/alerts` | no |
| UC-309 | ROUTE | `/alerts/<alert_id>/ack` | no |
| UC-309 | ROUTE | `/status` | no |
| UC-309 | ROUTE | `/retention` | no |
| UC-309 | ROUTE | `/reset` | no |
| UC-317 | ROUTE | `/api/v1/schema` | no |
| UC-317 | ROUTE | `/api/v1/kernel/models` | no |
| UC-317 | ROUTE | `/api/v1/kernel/tools` | no |
| UC-317 | ROUTE | `/api/v1/kernel/roles` | no |
| UC-317 | ROUTE | `/api/v1/kernel/scheduler/status` | no |
| UC-317 | ROUTE | `/api/v1/kernel/sessions` | no |
| UC-317 | ROUTE | `/api/v1/kernel/chat` | no |
| UC-317 | ROUTE | `/api/v1/kernel/syscall` | no |
| UC-317 | ROUTE | `/api/v1/kernel/schedule` | no |
| UC-317 | ROUTE | `/api/v1/kernel/tools/call` | no |
| UC-317 | ROUTE | `/api/v1/kernel/storage` | no |
| UC-317 | ROUTE | `/api/v1/kernel/storage/<key>` | no |
| UC-317 | ROUTE | `/health` | no |
| UC-320 | ROUTE | `/health` | no |
| UC-320 | ROUTE | `/api/v1/auth/login` | no |
| UC-320 | ROUTE | `/api/v1/auth/whoami` | no |
| UC-320 | ROUTE | `/api/v1/auth/logout` | no |
| UC-320 | ROUTE | `/api/v1/auth/status` | no |
| UC-320 | ROUTE | `/api/v1/auth/sessions` | no |
| UC-320 | ROUTE | `/api/v1/schema` | no |
| UC-320 | ROUTE | `/api/v1/models` | no |
| UC-320 | ROUTE | `/api/v1/templates` | no |
| UC-320 | ROUTE | `/api/v1/templates/<template_id>` | no |
| UC-320 | ROUTE | `/api/v1/sentiment` | no |
| UC-320 | ROUTE | `/api/v1/embedding` | no |
| UC-320 | ROUTE | `/api/v1/classify` | no |
| UC-320 | ROUTE | `/api/v1/benchmark` | no |
| UC-320 | ROUTE | `/api/v1/training/submit` | no |
| UC-320 | ROUTE | `/api/v1/training/run` | no |
| UC-320 | ROUTE | `/api/v1/training/promote` | no |
| UC-320 | ROUTE | `/api/v1/training/jobs` | no |
| UC-320 | ROUTE | `/api/v1/audit` | no |
| UC-320 | ROUTE | `/api/v1/hf/status` | no |
| UC-320 | ROUTE | `/api/v1/endpoints` | no |
| UC-320 | ROUTE | `/api/v1/endpoints` | no |
| UC-320 | ROUTE | `/api/v1/endpoints/<endpoint_id>/health` | no |
| UC-320 | ROUTE | `/api/v1/endpoints/<endpoint_id>/stop` | no |
| UC-320 | ROUTE | `/api/v1/endpoints/<endpoint_id>` | no |
| UC-320 | ROUTE | `/api/v1/datasets` | no |
| UC-320 | ROUTE | `/api/v1/datasets/load` | no |
| UC-320 | ROUTE | `/api/v1/datasets/validate` | no |
| UC-320 | ROUTE | `/api/v1/datasets/transform` | no |
| UC-320 | ROUTE | `/api/v1/trainer/train` | no |
| UC-320 | ROUTE | `/api/v1/trainer/jobs` | no |
| UC-320 | ROUTE | `/api/v1/peft/adapters` | no |
| UC-320 | ROUTE | `/api/v1/peft/adapters` | no |
| UC-320 | ROUTE | `/api/v1/peft/adapters/<adapter_id>/save` | no |
| UC-320 | ROUTE | `/api/v1/evaluate/compute` | no |
| UC-320 | ROUTE | `/api/v1/evaluate/compare` | no |
| UC-320 | ROUTE | `/api/v1/evaluate/results` | no |
| UC-320 | ROUTE | `/api/v1/spaces` | no |
| UC-320 | ROUTE | `/api/v1/spaces` | no |
| UC-320 | ROUTE | `/api/v1/spaces/<space_id>/stop` | no |
| UC-320 | ROUTE | `/api/v1/spaces/<space_id>` | no |
| UC-320 | ROUTE | `/api/v1/model-cards` | no |
| UC-320 | ROUTE | `/api/v1/model-cards` | no |
| UC-320 | ROUTE | `/api/v1/model-cards/<path:model_id>` | no |
| UC-320 | ROUTE | `/api/v1/model-cards/<path:model_id>/markdown` | no |
| UC-320 | ROUTE | `/api/v1/model-cards/<path:model_id>/approve` | no |
| UC-320 | ROUTE | `/api/v1/model-cards/<path:model_id>/push` | no |
| UC-320 | ROUTE | `/api/v1/catalog/models` | no |
| UC-320 | ROUTE | `/api/v1/catalog/datasets` | no |
| UC-320 | ROUTE | `/api/v1/catalog/spaces` | no |
| UC-320 | ROUTE | `/api/v1/catalog/search` | no |
| UC-320 | ROUTE | `/api/v1/catalog/models/<path:model_id>` | no |
| UC-320 | ROUTE | `/api/v1/catalog/datasets/<path:dataset_id>` | no |
| UC-320 | ROUTE | `/api/v1/catalog/spaces/<path:space_id>` | no |
| UC-320 | ROUTE | `/api/v1/catalog/models/<path:model_id>/gated` | no |
| UC-320 | ROUTE | `/api/v1/download/<path:repo_id>/resolve` | no |
| UC-320 | ROUTE | `/api/v1/download/<path:repo_id>/files` | no |
| UC-320 | ROUTE | `/api/v1/download/<path:repo_id>/info` | no |
| UC-320 | ROUTE | `/api/v1/download/<path:repo_id>/snippets` | no |
| UC-320 | ROUTE | `/api/v1/finetune/generate` | no |
| UC-320 | ROUTE | `/api/v1/auth/oauth/login` | no |
| UC-320 | ROUTE | `/api/v1/auth/oauth/callback` | no |
| UC-320 | ROUTE | `/api/v1/auth/oauth/scopes` | no |
| UC-320 | ROUTE | `/api/v1/panel/<path:model_id>` | no |
| UC-320 | ROUTE | `/api/v1/panel/<path:model_id>/vram` | no |
| UC-320 | ROUTE | `/api/v1/panel/<path:model_id>/vram/estimate` | no |
| UC-320 | ROUTE | `/api/v1/panel/<path:model_id>/playground` | no |
| UC-320 | ROUTE | `/api/v1/panel/<path:model_id>/license` | no |
| UC-320 | ROUTE | `/api/v1/panel/<path:model_id>/k8s-manifest` | no |
| UC-320 | ROUTE | `/api/v1/panel/<path:model_id>/benchmarks` | no |
| UC-320 | ROUTE | `/api/v1/panel/benchmarks/compare` | no |
| UC-320 | ROUTE | `/api/v1/panel/<path:model_id>/lineage` | no |
| UC-320 | ROUTE | `/api/v1/panel/<path:model_id>/lineage/register` | no |
| UC-320 | ROUTE | `/api/v1/panel/<path:model_id>/training-history` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/execute` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/pkce` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/jwt/validate` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/secrets` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/secrets` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/secrets/<secret_name>` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/preflight` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/cluster/nodes` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/manifest/vllm` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/manifest/pytorchjob` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/manifest/rayjob` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/manifest/pvc` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/apply` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/cache/check` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/cache` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/cache/prefetch` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/jobs` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/jobs/<job_name>/metrics` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/jobs/<job_name>/metrics/subscribe` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/package` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/publish` | no |
| UC-320 | ROUTE | `/api/v1/pipeline/cleanup` | no |
| UC-322 | ROUTE | `/health` | no |
| UC-322 | ROUTE | `/api/v1/schema` | no |
| UC-322 | ROUTE | `/` | no |
| UC-322 | ROUTE | `/api/v1/conflicts/resolve` | no |
| UC-322 | ROUTE | `/api/v1/reputation/record` | no |
| UC-322 | ROUTE | `/api/v1/reputation/ranking` | no |
| UC-322 | ROUTE | `/api/v1/reputation/<agent_id>` | no |
| UC-322 | ROUTE | `/api/v1/duplicate/check` | no |
| UC-322 | ROUTE | `/api/v1/deadlock/check` | no |
| UC-322 | ROUTE | `/api/v1/conflicts/history` | no |
| UC-322 | ROUTE | `/api/v1/escalation/history` | no |
| UC-322 | ROUTE | `/api/v1/escalation/circuit-breaker` | no |
| UC-322 | ROUTE | `/api/v1/escalation/circuit-breaker/reset` | no |
| UC-322 | ROUTE | `/api/v1/observability/summary` | no |
| UC-322 | ROUTE | `/api/v1/observability/logs` | no |
| UC-322 | ROUTE | `/api/v1/observability/spans` | no |
| UC-322 | ROUTE | `/metrics` | no |
| UC-322 | ROUTE | `/api/v1/tasks/active` | no |
| UC-324 | ROUTE | `/` | no |
| UC-324 | ROUTE | `/health` | no |
| UC-324 | ROUTE | `/api/v1/schema` | no |
| UC-324 | ROUTE | `/api/v1/containment/orchestrate` | no |
| UC-324 | ROUTE | `/api/v1/containment/check` | no |
| UC-324 | ROUTE | `/api/v1/containment/stress-test` | no |
| UC-324 | ROUTE | `/api/v1/containment/red-team` | no |
| UC-324 | ROUTE | `/api/v1/containment/red-team-eval` | no |
| UC-324 | ROUTE | `/api/v1/containment/post-check` | no |
| UC-324 | ROUTE | `/api/v1/containment/monitor-status` | no |
| UC-324 | ROUTE | `/api/v1/containment/circuit-breaker` | no |
| UC-324 | ROUTE | `/api/v1/containment/sign-intent` | no |
| UC-324 | ROUTE | `/api/v1/containment/verify-intent` | no |
| UC-324 | ROUTE | `/api/v1/containment/scan-content` | no |
| UC-324 | ROUTE | `/api/v1/containment/llm-judge` | no |
| UC-324 | ROUTE | `/api/v1/containment/devops-guardrails` | no |
| UC-324 | ROUTE | `/api/v1/containment/llm-guardrails` | no |
| UC-324 | ROUTE | `/api/v1/containment/trajectory-eval` | no |
| UC-324 | ROUTE | `/api/v1/containment/stage-wise-eval` | no |
| UC-324 | ROUTE | `/api/v1/containment/kill-switch` | no |
| UC-324 | ROUTE | `/api/v1/containment/safe-shutdown` | no |
| UC-324 | ROUTE | `/api/v1/containment/safe-hold` | no |
| UC-324 | ROUTE | `/api/v1/containment/resume-safe-hold` | no |
| UC-324 | ROUTE | `/api/v1/containment/shutdown-status` | no |
| UC-324 | ROUTE | `/api/v1/containment/shutdown-postmortem` | no |
| UC-324 | ROUTE | `/api/v1/containment/shutdown-evidence` | no |
| UC-324 | ROUTE | `/api/v1/containment/reactivation-request` | no |
| UC-324 | ROUTE | `/api/v1/containment/audit` | no |
| UC-324 | ROUTE | `/api/v1/containment/sre-status` | no |
| UC-325 | ROUTE | `/health` | no |
| UC-325 | ROUTE | `/api/v1/schema` | no |
| UC-325 | ROUTE | `/` | no |
| UC-325 | ROUTE | `/api/v1/reasoning/run` | no |
| UC-325 | ROUTE | `/api/v1/reasoning/evaluate` | no |
| UC-325 | ROUTE | `/api/v1/reasoning/detect-hallucinations` | no |
| UC-325 | ROUTE | `/api/v1/reasoning/refine-query` | no |
| UC-325 | ROUTE | `/api/v1/reasoning/history` | no |
| UC-325 | ROUTE | `/api/v1/observability/summary` | no |
| UC-325 | ROUTE | `/api/v1/observability/logs` | no |
| UC-325 | ROUTE | `/api/v1/observability/spans` | no |
| UC-325 | ROUTE | `/metrics` | no |
| UC-326 | ROUTE | `/health` | no |
| UC-326 | ROUTE | `/` | no |
| UC-326 | ROUTE | `/api/v1/schema` | no |
| UC-326 | ROUTE | `/api/v1/maqri/search` | no |
| UC-326 | ROUTE | `/api/v1/maqri/documents` | no |
| UC-326 | ROUTE | `/api/v1/maqri/experience` | no |
| UC-326 | ROUTE | `/api/v1/maqri/critic` | no |
| UC-326 | ROUTE | `/api/v1/maqri/refine` | no |
| UC-326 | ROUTE | `/api/v1/maqri/history` | no |
| UC-326 | ROUTE | `/api/v1/maqri/stats` | no |
| UC-326 | ROUTE | `/api/v1/maqri/logs` | no |
| UC-326 | ROUTE | `/api/v1/maqri/spans` | no |
| UC-326 | ROUTE | `/metrics` | no |
| UC-326 | ROUTE | `/api/v1/maqri/governed/submit` | no |
| UC-326 | ROUTE | `/api/v1/maqri/governed/validate` | no |
| UC-326 | ROUTE | `/api/v1/maqri/governed` | no |
| UC-328 | ROUTE | `/health` | no |
| UC-328 | ROUTE | `/` | no |
| UC-328 | ROUTE | `/api/v1/schema` | no |
| UC-328 | ROUTE | `/api/v1/orquesta/execute` | no |
| UC-328 | ROUTE | `/api/v1/orquesta/sources` | no |
| UC-328 | ROUTE | `/api/v1/orquesta/cache/invalidate` | no |
| UC-328 | ROUTE | `/api/v1/orquesta/stats` | no |
| UC-328 | ROUTE | `/api/v1/orquesta/logs` | no |
| UC-328 | ROUTE | `/api/v1/orquesta/spans` | no |
| UC-328 | ROUTE | `/metrics` | no |
| UC-329 | ROUTE | `/health` | no |
| UC-329 | ROUTE | `/` | no |
| UC-329 | ROUTE | `/api/v1/schema` | no |
| UC-329 | ROUTE | `/api/v1/graphrag-got/ingest` | no |
| UC-329 | ROUTE | `/api/v1/graphrag-got/reason` | no |
| UC-329 | ROUTE | `/api/v1/graphrag-got/feedback` | no |
| UC-329 | ROUTE | `/api/v1/graphrag-got/stats` | no |
| UC-329 | ROUTE | `/api/v1/graphrag-got/logs` | no |
| UC-329 | ROUTE | `/api/v1/graphrag-got/spans` | no |
| UC-329 | ROUTE | `/metrics` | no |
| UC-330 | ROUTE | `/health` | no |
| UC-330 | ROUTE | `/` | no |
| UC-330 | ROUTE | `/api/v1/schema` | no |
| UC-330 | ROUTE | `/api/v1/balance-ex/decide` | no |
| UC-330 | ROUTE | `/api/v1/balance-ex/update` | no |
| UC-330 | ROUTE | `/api/v1/balance-ex/episode` | no |
| UC-330 | ROUTE | `/api/v1/balance-ex/stats` | no |
| UC-330 | ROUTE | `/api/v1/balance-ex/recommend` | no |
| UC-330 | ROUTE | `/api/v1/balance-ex/reset` | no |
| UC-330 | ROUTE | `/metrics` | no |
| UC-703 | GET | `/health` | no |
| UC-703 | GET | `/api/v1/cards` | no |
| UC-703 | POST | `/api/v1/objective` | no |
| UC-703 | POST | `/api/v1/objective/<task_id>/plan` | no |
| UC-703 | POST | `/api/v1/objective/<task_id>/approve` | no |
| UC-703 | POST | `/api/v1/objective/<task_id>/approve/<step_id>` | no |
| UC-703 | POST | `/api/v1/objective/<task_id>/execute` | no |
| UC-703 | POST | `/api/v1/objective/<task_id>/pause` | no |
| UC-703 | POST | `/api/v1/objective/<task_id>/resume` | no |
| UC-703 | POST | `/api/v1/objective/<task_id>/cancel` | no |
| UC-703 | GET | `/api/v1/objective/<task_id>` | no |
| UC-703 | GET | `/api/v1/objectives` | no |
| UC-703 | GET | `/api/v1/runtime/status` | no |
| UC-703 | POST | `/api/v1/temporal/workflow` | no |
| UC-703 | POST | `/api/v1/temporal/workflow/<workflow_id>/run` | no |
| UC-703 | POST | `/api/v1/temporal/workflow/<workflow_id>/signal` | no |
| UC-703 | POST | `/api/v1/stackstorm/execute` | no |
| UC-703 | POST | `/api/v1/n8n/execute` | no |
| UC-703 | GET | `/api/v1/metrics` | no |
| UC-703 | POST | `/api/v1/ft/curate-and-register` | no |
| UC-703 | POST | `/api/v1/ft/plan-resources` | no |
| UC-703 | POST | `/api/v1/ft/run-hp-search` | no |
| UC-703 | POST | `/api/v1/ft/create-training-config` | no |
| UC-703 | POST | `/api/v1/ft/simulate-training-step` | no |
| UC-703 | POST | `/api/v1/ft/evaluate` | no |
| UC-703 | POST | `/api/v1/ft/alignment-recommendation` | no |
| UC-703 | POST | `/api/v1/ft/deploy-canary` | no |
| UC-703 | POST | `/api/v1/ft/assess-canary` | no |
| UC-703 | POST | `/api/v1/ft/detect-drift` | no |
| UC-703 | POST | `/api/v1/ft/feedback` | no |
| UC-703 | GET | `/api/v1/ft/pipelines/<pipeline_id>` | no |
| UC-703 | GET | `/api/v1/ft/pipelines` | no |
| UC-703 | POST | `/api/v1/ft/privacy/apply-contract` | no |
| UC-703 | POST | `/api/v1/ft/privacy/deidentify` | no |
| UC-703 | POST | `/api/v1/ft/privacy/dp-config` | no |
| UC-703 | POST | `/api/v1/ft/privacy/apply-dp` | no |
| UC-703 | POST | `/api/v1/ft/privacy/membership-inference` | no |
| UC-703 | POST | `/api/v1/ft/privacy/network-policy` | no |
| UC-703 | POST | `/api/v1/ft/privacy/encryption-lease` | no |
| UC-703 | POST | `/api/v1/ft/privacy/inference-preflight` | no |
| UC-703 | POST | `/api/v1/ft/privacy/inference-postflight` | no |
| UC-703 | POST | `/api/v1/ft/privacy/artifacts` | no |
| UC-703 | GET | `/api/v1/ft/privacy/pipelines/<pipeline_id>` | no |
| UC-703 | POST | `/api/v1/ft/quality-gate/run` | no |
| UC-703 | POST | `/api/v1/ft/quality-gate/approve` | no |
| UC-703 | GET | `/api/v1/ft/quality-gate/reports/<report_id>` | no |
| UC-703 | GET | `/api/v1/ft/quality-gate/reports` | no |
| UC-703 | POST | `/api/v1/ft/extrinsic-metrics/app-event` | no |
| UC-703 | POST | `/api/v1/ft/extrinsic-metrics/inf-event` | no |
| UC-703 | POST | `/api/v1/ft/extrinsic-metrics/compute` | no |
| UC-703 | GET | `/api/v1/ft/extrinsic-metrics/prometheus` | no |
| UC-703 | GET | `/api/v1/ft/extrinsic-metrics/logs` | no |
| UC-703 | GET | `/api/v1/ft/extrinsic-metrics/sessions/<session_id>` | no |
| UC-703 | POST | `/api/v1/ft/evaluation-matrix/checkpoint` | no |
| UC-703 | GET | `/api/v1/ft/evaluation-matrix/checkpoints` | no |
| UC-703 | POST | `/api/v1/ft/evaluation-matrix/prompt` | no |
| UC-703 | POST | `/api/v1/ft/evaluation-matrix/golden-set` | no |
| UC-703 | POST | `/api/v1/ft/evaluation-matrix/evaluate` | no |
| UC-703 | POST | `/api/v1/ft/evaluation-matrix/human-review` | no |
| UC-703 | POST | `/api/v1/ft/evaluation-matrix/user-feedback` | no |
| UC-703 | GET | `/api/v1/ft/evaluation-matrix/reports/<report_id>` | no |
| UC-703 | GET | `/api/v1/ft/evaluation-matrix/prometheus` | no |
| UC-703 | GET | `/api/v1/ft/evaluation-matrix/logs` | no |
| UC-703 | POST | `/api/v1/runtime/recovery/register-tool` | no |
| UC-703 | POST | `/api/v1/runtime/recovery/invoke` | no |
| UC-703 | GET | `/api/v1/runtime/recovery/reports/<report_id>` | no |
| UC-703 | GET | `/api/v1/runtime/recovery/reports` | no |
| UC-703 | GET | `/api/v1/runtime/recovery/prometheus` | no |
| UC-703 | GET | `/api/v1/runtime/recovery/logs` | no |
| UC-703 | POST | `/api/v1/runtime/recovery/hitl-decide` | no |
| UC-703 | POST | `/api/v1/compliance/prompt/commit` | no |
| UC-703 | POST | `/api/v1/compliance/prompt/approve` | no |
| UC-703 | GET | `/api/v1/compliance/prompt/history/<prompt_name>` | no |
| UC-703 | POST | `/api/v1/compliance/dataset/register` | no |
| UC-703 | POST | `/api/v1/compliance/dataset/transformation` | no |
| UC-703 | GET | `/api/v1/compliance/dataset/<dataset_id>` | no |
| UC-703 | POST | `/api/v1/compliance/access/grant` | no |
| UC-703 | POST | `/api/v1/compliance/access/evaluate` | no |
| UC-703 | POST | `/api/v1/compliance/inference/record` | no |
| UC-703 | GET | `/api/v1/compliance/inference/query` | no |
| UC-703 | GET | `/api/v1/compliance/ledger/verify` | no |
| UC-703 | POST | `/api/v1/compliance/metrics/ingest` | no |
| UC-703 | POST | `/api/v1/compliance/alerts/acknowledge` | no |
| UC-703 | GET | `/api/v1/compliance/report` | no |
| UC-703 | GET | `/api/v1/compliance/dashboard` | no |
| UC-703 | GET | `/api/v1/compliance/rules` | no |
| UC-703 | POST | `/api/v1/ci/feedback` | no |
| UC-703 | POST | `/api/v1/ci/analyze` | no |
| UC-703 | POST | `/api/v1/ci/recommendations/approve` | no |
| UC-703 | POST | `/api/v1/ci/recommendations/reject` | no |
| UC-703 | GET | `/api/v1/ci/recommendations` | no |
| UC-703 | GET | `/api/v1/ci/recommendations/pending` | no |
| UC-703 | POST | `/api/v1/ci/baseline` | no |
| UC-703 | POST | `/api/v1/ci/measure` | no |
| UC-703 | GET | `/api/v1/ci/dashboard` | no |
| UC-703 | POST | `/api/v1/qa/run` | no |
| UC-703 | POST | `/api/v1/incidents` | no |
| UC-703 | GET | `/api/v1/incidents` | no |
| UC-703 | GET | `/api/v1/incidents/<incident_id>` | no |
| UC-703 | POST | `/api/v1/incidents/<incident_id>/triage` | no |
| UC-703 | POST | `/api/v1/incidents/<incident_id>/contain` | no |
| UC-703 | POST | `/api/v1/incidents/<incident_id>/resolve` | no |
| UC-703 | POST | `/api/v1/incidents/<incident_id>/alerts` | no |
| UC-703 | POST | `/api/v1/incidents/oncall` | no |
| UC-703 | POST | `/api/v1/incidents/<incident_id>/communicate` | no |
| UC-703 | POST | `/api/v1/incidents/<incident_id>/runbook` | no |
| UC-703 | POST | `/api/v1/incidents/<incident_id>/post-mortem` | no |
| UC-703 | POST | `/api/v1/incidents/slos` | no |
| UC-703 | POST | `/api/v1/incidents/sli/register` | no |
| UC-703 | POST | `/api/v1/incidents/slos/<slo_id>/sample` | no |
| UC-703 | GET | `/api/v1/incidents/dashboard` | no |
| UC-703 | POST | `/api/v1/aiops/events` | no |
| UC-703 | POST | `/api/v1/aiops/correlate` | no |
| UC-703 | POST | `/api/v1/aiops/groups/<group_id>/process` | no |
| UC-703 | POST | `/api/v1/aiops/pipeline` | no |
| UC-703 | POST | `/api/v1/aiops/policies` | no |
| UC-703 | GET | `/api/v1/aiops/dashboard` | no |
| UC-703 | POST | `/api/v1/rbac/roles` | no |
| UC-703 | POST | `/api/v1/rbac/permissions` | no |
| UC-703 | POST | `/api/v1/rbac/principals` | no |
| UC-703 | POST | `/api/v1/rbac/resources` | no |
| UC-703 | POST | `/api/v1/rbac/sod` | no |
| UC-703 | POST | `/api/v1/rbac/access` | no |
| UC-703 | POST | `/api/v1/rbac/approvals` | no |
| UC-703 | POST | `/api/v1/rbac/approvals/<request_id>/approve` | no |
| UC-703 | POST | `/api/v1/rbac/approvals/<request_id>/reject` | no |
| UC-703 | POST | `/api/v1/audit/events` | no |
| UC-703 | GET | `/api/v1/audit/query` | no |
| UC-703 | GET | `/api/v1/audit/verify` | no |
| UC-703 | GET | `/api/v1/rbac/dashboard` | no |
| UC-703 | POST | `/api/v1/serving/sessions` | no |
| UC-703 | POST | `/api/v1/serving/chat` | no |
| UC-703 | POST | `/api/v1/serving/chat/enterprise` | no |
| UC-703 | POST | `/api/v1/serving/tokens` | no |
| UC-703 | POST | `/api/v1/serving/feedback` | no |
| UC-703 | POST | `/api/v1/serving/re-evaluate/<request_id>` | no |
| UC-703 | GET | `/api/v1/serving/dashboard` | no |
| UC-703 | POST | `/api/v1/postmortem/incidents` | no |
| UC-703 | POST | `/api/v1/postmortem/incidents/<record_id>/analyze` | no |
| UC-703 | POST | `/api/v1/postmortem/incidents/<record_id>/run` | no |
| UC-703 | POST | `/api/v1/postmortem/hypotheses/<hypothesis_id>/approve` | no |
| UC-703 | POST | `/api/v1/postmortem/proposals/<proposal_id>/approve` | no |
| UC-703 | POST | `/api/v1/postmortem/proposals/<proposal_id>/reject` | no |
| UC-703 | GET | `/api/v1/postmortem/dashboard` | no |

## 3. Flujo vertical end-to-end

```text
Datos (UC-292/UC-294) → normalización (UC-309/UC-703) → RAG/memoria (UC-251/UC-296/UC-329)
  → análisis fundamental/técnico (UC-701/UC-702) → predicción ASK/BID (UC-279/UC-280/UC-283)
  → razonamiento (UC-314/UC-315/UC-322) → HITL (UC-290) → gateway (UC-300)
  → autorización/RBAC (UC-703 rbac_audit) → ejecución simulada (UC-317/UC-703 production_serving)
  → observación (UC-309/UC-308) → auditoría (UC-703 audit_ledger) → feedback (UC-087/UC-703 feedback_loop)
  → post-mortem (UC-703 postmortem_loop) → entrenamiento continuo (UC-075/UC-179/UC-320)
```

## 4. Flujos horizontales clave

| Origen | Destino | Propósito |
|---|---|---|
| UC-315 (orquestador cognitivo) | UC-290 (HITL guardian) | revisión antes de ejecución |
| UC-290 (HITL) | UC-300 (secure gateway) | capability token con dossier_hash |
| UC-300 (gateway) | UC-317 / UC-703 (runtime/ejecución) | ejecución autorizada en sandbox |
| UC-317 / UC-703 | UC-309 (observability) | métricas, trazas y logs |
| UC-309 / UC-703 | UC-703 (audit_ledger) | registro inmutable |
| UC-703 (postmortem_loop) | UC-703 (feedback_loop) | casos anti-regresión |
| UC-075 / UC-179 / UC-320 | UC-317 / UC-703 | promoción canary de modelos |
| UC-324 (contención) | UC-315 / UC-317 / UC-300 | kill switch y rollback |

## 5. Matriz de dependencias entre UCs

| Consumidor | Productor | Tipo | Notas |
|---|---|---|---|
| UC-290 HITL | UC-315 decisiones | request | requiere dossier + confidence |
| UC-300 gateway | UC-290 approval | token | capability_token one-use TTL |
| UC-317 runtime | UC-300 token | execution | sandbox, dry-run |
| UC-703 serving | UC-703 RBAC | authz | roles/scopes + rate limit |
| UC-703 postmortem | UC-703 serving/observability | events | registros inmutables |
| UC-075 training | UC-087 feedback | data | HITL labels + golden dataset |
| UC-320 LoRA/quant | UC-075/UC-179 | artifact | release gate |
