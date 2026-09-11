# UC_SECURITY_THREAT_MODEL.md

## Amenazas y controles observados

| Amenaza | UCs con control | Estado |
|---|---|---|
| Inyección de prompt | UC-119, UC-290, UC-300, UC-703 guardrails | implementado parcial |
| Escalamiento de privilegios | UC-300, UC-703 rbac_audit | implementado |
| Ejecución no autorizada | UC-290, UC-300, UC-703 approval_workflow | implementado |
| Falsificación de action_hash / approval_ref | UC-300 capability_token, UC-703 audit_ledger | implementado |
| Data poisoning / envenenamiento | UC-119, UC-308, UC-703 postmortem_loop | revisión periódica |
| Exfiltración de PII/secrets | UC-119, UC-290, UC-703 guardrails | revisar logs |
| SSRF en tool calls | UC-300 allowlist, UC-324 sandbox | implementado |
| Condición de carrera en aprobaciones | UC-300 TOCTOU, UC-703 approval workflow | implementado |

## Controles transversales

- RBAC/ABAC en UC-300 y UC-703.
- HITL con dossier_hash en UC-290.
- Capability tokens TTL y one-use en UC-300.
- Ledger inmutable con hash-chain en UC-703.
- Sandbox y kill switch en UC-324.
- Observabilidad en UC-309/UC-703.
