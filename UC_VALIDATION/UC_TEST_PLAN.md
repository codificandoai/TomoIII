# UC_TEST_PLAN.md

## Plan de pruebas reproducible

### Fases
1. Fase 1: descubrimiento (inventory.py) → `UC_VALIDATION/uc_inventory.json`
2. Fase 2: pruebas de contrato por endpoint usando INPUT_CARDS
3. Fase 3: integración entre UCs (flujo vertical/horizontal)
4. Fase 4: validación de datos y predicción
5. Fase 5: pruebas de seguridad con payloads adversariales
6. Fase 6: caos y carga

### Comando de ejecución por UC
```bash
cd UC-XXX/code && python -m pytest tests -q
```

### UCs con tests existentes

| UC | Nº tests | Notas |
|---|---|---|
| UC-075 | 0 |  |
| UC-083 | 0 |  |
| UC-087 | 2 | test_mlops_hitl_feedback_loop.py; test_mlops_self_healing.py |
| UC-119 | 10 | test_api_integration.py; test_bias.py; test_cost.py... |
| UC-127 | 6 | test_api_integration.py; test_chaos_engineering.py; test_classifier.py... |
| UC-129 | 4 | test_api_integration.py; test_classifier.py; test_connectors.py... |
| UC-162 | 0 |  |
| UC-179 | 7 | test_api_integration.py; test_data_collector.py; test_deployment_manager.py... |
| UC-251 | 6 | test_api.py; test_chunker.py; test_pipeline.py... |
| UC-257 | 4 | test_adapters.py; test_api.py; test_orchestrator.py... |
| UC-258 | 3 | test_agent.py; test_api.py; test_environments.py |
| UC-259 | 4 | test_api.py; test_graph.py; test_safety.py... |
| UC-260 | 4 | test_api.py; test_bdi.py; test_predictor.py... |
| UC-261 | 6 | test_adaptive.py; test_api.py; test_bdi.py... |
| UC-262 | 3 | test_api.py; test_cognitive.py; test_evolution.py |
| UC-263 | 4 | test_api.py; test_environment.py; test_graph.py... |
| UC-264 | 5 | test_api.py; test_graph.py; test_planner.py... |
| UC-265 | 10 | test_api.py; test_enhancements.py; test_graph.py... |
| UC-266 | 11 | test_api.py; test_enhancements.py; test_graph.py... |
| UC-268 | 3 | test_api.py; test_bus_and_agents.py; test_security.py |
| UC-269 | 2 | test_api.py; test_contract_net.py |
| UC-270 | 5 | test_api.py; test_detector.py; test_negotiation.py... |
| UC-271 | 5 | test_api.py; test_hpa.py; test_manifests.py... |
| UC-272 | 5 | test_api.py; test_blackboard.py; test_gossip.py... |
| UC-273 | 6 | test_api.py; test_crypto.py; test_guardrails.py... |
| UC-274 | 6 | test_api.py; test_blockchain.py; test_consensus.py... |
| UC-275 | 7 | test_api.py; test_critic.py; test_evaluator.py... |
| UC-276 | 6 | test_api.py; test_models.py; test_quality.py... |
| UC-277 | 8 | test_api.py; test_embeddings.py; test_episodic.py... |
| UC-279 | 3 | test_api.py; test_core.py; test_pricing_engine.py |
| UC-280 | 3 | test_api.py; test_executor.py; test_planners.py |
| UC-281 | 2 | test_api.py; test_orchestrator.py |
| UC-283 | 2 | test_api.py; test_loop.py |
| UC-284 | 2 | test_api.py; test_middleware.py |
| UC-289 | 2 | test_api.py; test_governance.py |
| UC-290 | 0 |  |
| UC-292 | 18 | test_api.py; test_brain.py; test_central_brain.py... |
| UC-293 | 20 | test_adversarial_juice.py; test_api.py; test_bdi.py... |
| UC-294 | 21 | test_adversarial_juice.py; test_api.py; test_bdi.py... |
| UC-295 | 22 | test_adversarial_juice.py; test_api.py; test_bdi.py... |
| UC-296 | 24 | test_adversarial_juice.py; test_api.py; test_bdi.py... |
| UC-300 | 0 |  |
| UC-307 | 4 | test_api.py; test_decision_engine.py; test_evaluator.py... |
| UC-308 | 0 |  |
| UC-309 | 0 |  |
| UC-313 | 32 | test_adversarial_juice.py; test_api.py; test_api_plasticity.py... |
| UC-314 | 4 | test_api.py; test_causal_model.py; test_evaluator.py... |
| UC-315 | 34 | test_adversarial_juice.py; test_api.py; test_api_plasticity.py... |
| UC-317 | 4 | test_api.py; test_kernel.py; test_kernel_shutdown.py... |
| UC-320 | 7 | test_api.py; test_auth.py; test_catalog.py... |
| UC-322 | 0 |  |
| UC-324 | 3 | test_containment.py; test_llm_private_gateway.py; test_safe_shutdown.py |
| UC-325 | 0 |  |
| UC-326 | 0 |  |
| UC-328 | 0 |  |
| UC-329 | 0 |  |
| UC-330 | 0 |  |
| UC-700 | 2 | test_api.py; test_core.py |
| UC-701 | 3 | test_api.py; test_core.py; test_emis_scraper.py |
| UC-702 | 5 | test_api.py; test_capacity_pool.py; test_resource_monitor.py... |
| UC-703 | 15 | test_aiops_self_healing.py; test_compliance_as_code.py; test_continuous_improvement.py... |

### Próximas pruebas a implementar
- Generador de contratos a partir de INPUT_CARDS.
- Tests adversariales para cada endpoint de UC-290/UC-300/UC-703.
- Validación de hash-chain del ledger.
- Walk-forward leakage tests en UCs financieras.
