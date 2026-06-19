# ADR 0003 - EMR Deployment Mode: EC2 with Spot (current) -> Serverless (target)

- **Status:** Accepted (current EC2 + Graviton), Planned migration to Serverless in H2
- **Date:** 2026-05-19 (revised 2026-06-17: m5.large -> Graviton m7g.xlarge)
- **Deciders:** mzanferrari

## Context

The pipeline runs sporadically: a portfolio demo executes ~10 times/month, each run ~15 minutes of Spark work over ~63 MB of input. The previous configuration (m5.4xlarge master + 2× m5.2xlarge core, all On-Demand) cost ~$1.92/h and was massively oversized.

Three EMR deployment modes considered:

1. **EMR on EC2** - classic. Cluster of EC2 instances. Full control. Bootstrap actions, custom AMIs.
2. **EMR on EKS** - Spark in containers on Kubernetes. Shared infrastructure across workloads.
3. **EMR Serverless** - fully managed. No cluster sizing, per-second billing of vCPU/RAM consumed.

## Decision

**Current state (H1):** EMR on EC2 with right-sized On-Demand master + Spot core nodes.

```hcl
master_instance_group { instance_type = "m7g.xlarge" }
core_instance_group   { instance_type = "m7g.xlarge"; instance_count = 1; bid_price = "0.164" }
auto_termination_policy { idle_timeout = 600 }
```

**Target state (H2):** EMR Serverless as the default deployment mode, with EC2 retained as opt-in for cluster-control demonstrations.

## Rationale

### Cost comparison for this workload

Per run (15 min Spark work + 5 min cluster startup, sporadic schedule):

| Mode | Compute config | Cost/run | Notes |
|---|---|---|---|
| **EC2 On-Demand (original)** | m5.4xlarge + 2× m5.2xlarge | ~$0.50 | Cluster startup wastes ~5 min of full-capacity billing |
| **EC2 right-sized + Spot (Graviton)** | m7g.xlarge master + 1× m7g.xlarge Spot | ~$0.16 | ARM; ~11% cheaper Spot than x86 equivalent |
| **EMR Serverless** | 4 workers × 4 vCPU × 16 GB on demand | ~$0.14 | No idle cluster, scales per-stage |
| **EKS on Fargate** | Same workers | ~$0.15 | Plus EKS cluster fee - only justified if multi-tenant |

### Instance family: the m5.large dead end, and Graviton

The original right-sizing specified `m5.large` core nodes - the smallest m5 size, chosen to minimise cost. The real deployment revealed that EMR does not support `m5.large`: the minimum supported size in every modern family is `xlarge` (verified with `aws emr list-supported-instance-types --release-label emr-7.13.0`, which lists `m5.xlarge`, `m6i.xlarge`, `m7g.xlarge`, ... but no `*.large`).

Since cost could not be reduced by going smaller, it was reduced by changing architecture: Graviton (ARM) `m7g.xlarge`. Measured on-account (eu-west-1, 2026-06-17): Spot `m7g.xlarge` ~$0.082/h vs `m5.xlarge` x86 ~$0.092/h (~11% cheaper on Spot); On-Demand $0.1632 vs `m7i.xlarge` $0.2016 (~19%). The bid price is set to $0.164 (the On-Demand price rounded up to EMR's 3-decimal limit) as a ceiling - Spot is paid at the real ~$0.082, the ceiling only guarantees allocation through price spikes. Core count drops to 1: one xlarge (4 vCPU) is ample for 63 MB of input, sized to the data rather than padded.

ARM compatibility was confirmed before migrating: numpy ships aarch64 wheels (pinned in uv.lock) and the bootstrap installs only pure-Python boto3.

### Beyond cost

| Factor | EC2 | Serverless | EKS |
|---|---|---|---|
| Cluster startup time | 5-7 min | <1 min | 2-3 min |
| Bootstrap script (custom packages) | Required | Pre-baked image | Custom image |
| Spot pricing | Available | Not supported | Available |
| Long-running clusters (>8h/day, predictable) | **Best** with RI/Savings Plan | More expensive | Mid |
| Sporadic workloads (<2h/day) | Wasteful | **Best** | Mid |
| FinOps discoverability | Complex (per-instance) | Simple (per-job) | Complex |
| Portfolio narrative | "I can manage a cluster" | "I size workloads economically" | "I run multi-tenant" |

### Why EC2 first, Serverless later

EC2 mode is kept as the H1 baseline because:

- The course material covered EMR on EC2. Migrating immediately would lose continuity with prior learning.
- EC2 mode forces explicit understanding of master/core/task topology, bootstrap, security groups - useful in interviews.
- Spot integration on EC2 demonstrates classical FinOps. Serverless hides this.

Serverless becomes default in H2 because:

- For sporadic workloads, Serverless wins on cost and operational simplicity.
- Removes ~150 lines of Terraform (no instance groups, no bootstrap, no security groups).
- "I migrated from EMR-on-EC2 to EMR Serverless because the workload was sporadic" is a stronger interview story than "I chose Serverless because tutorial said so".

### Why not EKS

EMR on EKS makes sense when:

- The team already operates an EKS cluster for other workloads (multi-tenant amortization)
- Strict containerization policy across all data workloads
- Need fine-grained pod-level isolation

None of these apply to a single-pipeline portfolio. Adding EKS adds operational complexity (cluster management, node groups, networking) without proportional gain.

## Consequences

**Accepted (current H1 with EC2 + Spot):**

- Spot interruption on core nodes can fail jobs. Spark handles retries gracefully for stateless map operations; less so for late-stage shuffles. Acceptable for portfolio demo.
- Cluster startup latency (5-7 min) per run feels slow for interactive iteration. Acceptable for batch.

**To be accepted (H2 with Serverless):**

- Less control over runtime environment (Serverless uses pre-baked images).
- No Spot discount; per-vCPU pricing is fixed.
- Cannot install arbitrary system packages without custom image (which has its own overhead).
- Trade-off documented in this ADR.

## Revisit Criteria

- If workload becomes daily/predictable (e.g., scheduled in Airflow with consistent execution): re-evaluate EC2 + Reserved Instances or Savings Plans.
- If job requires custom JNI libraries, native dependencies, or root-level system tweaks: stay on EC2 with custom AMI.
- If team adopts Kubernetes for other workloads: re-evaluate EMR on EKS.
