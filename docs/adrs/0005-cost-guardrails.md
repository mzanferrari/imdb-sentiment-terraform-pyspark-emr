# ADR 0005 - Cost Guardrails: Budget + Idle Alarm, No Killer Lambda

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** mzanferrari

## Context

The cluster incurs real charges. `auto_termination_policy` (idle 10 min) and `keep_job_flow_alive_when_no_steps = false` prevent a forgotten cluster, but nothing detects a failure of that prevention. A cost guardrail layer was added.

## Decision

Two layers, provisioned as code:

1. Account monthly budget (`modules/finops`) with SNS alerts at 80% forecast and 100% actual spend. Slow reactive backstop (billing metrics lag hours).
2. CloudWatch `IsIdle` alarm (`modules/emr`) firing after 15 minutes of idle. Fast detector if auto-termination ever fails.

A scheduled Lambda that force-terminates clusters past an absolute age was considered and deliberately not implemented.

## Consequences

- Two independent signals cover both runaway spend (budget) and a stuck cluster (IsIdle), at near-zero cost (alarms and budgets are free tier).
- The killer Lambda is omitted by proportionality: for a project running ~10 times/month, the three existing controls (auto-termination, idle alarm, budget) are sufficient. A Lambda adds an always-on component, an IAM role with terminate permissions, and its own failure surface - operational complexity exceeding the risk it removes.
- If usage profile changes (frequent or long-lived clusters), revisit: the absolute-age killer becomes justified when idle-based controls are not enough.
- The SNS cost-alerts topic is encrypted at rest with the AWS-managed key (alias/aws/sns). A customer-managed CMK was considered and rejected as disproportionate for non-sensitive budget notifications; the trivy AWS-0136 finding is suppressed with this rationale in infra/.trivyignore.

## Revisit when

Cluster frequency or lifetime grows beyond the sporadic demo profile.
