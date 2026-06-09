# ADR 0003 - EMR Deployment Mode: EC2 with Spot (current) -> Serverless (target)

- **Status:** Accepted (current EC2), Planned migration to Serverless in H2
- **Date:** 2026-05-19
- **Deciders:** mzanferrari

## Context

The pipeline runs sporadically: a portfolio demo executes ~10 times/month, each run ~15 minutes of Spark work over ~50 MB of input. The previous configuration (m5.4xlarge master + 2× m5.2xlarge core, all On-Demand) cost ~$1.92/h and was massively oversized.

Three EMR deployment modes considered:

1. **EMR on EC2** - classic. Cluster of EC2 instances. Full control. Bootstrap actions, custom AMIs.
2. **EMR on EKS** - Spark in containers on Kubernetes. Shared infrastructure across workloads.
3. **EMR Serverless** - fully managed. No cluster sizing, per-second billing of vCPU/RAM consumed.

## Decision

**Current state (H1):** EMR on EC2 with right-sized On-Demand master + Spot core nodes.

```hcl
master_instance_group { instance_type = "m5.xlarge" }
core_instance_group   { instance_type = "m5.large"; instance_count = 2; bid_price = "0.05" }
auto_termination_policy { idle_timeout = 600 }
```

**Target state (H2):** EMR Serverless as the default deployment mode, with EC2 retained as opt-in for cluster-control demonstrations.

## Rationale

### Cost comparison for this workload

Per run (15 min Spark work + 5 min cluster startup, sporadic schedule):

| Mode | Compute config | Cost/run | Notes |
|---|---|---|---|
| **EC2 On-Demand (original)** | m5.4xlarge + 2× m5.2xlarge | ~$0.50 | Cluster startup wastes ~5 min of full-capacity billing |
| **EC2 right-sized + Spot** | m5.xlarge + 2× m5.large Spot | ~$0.17 | Spot interruption risk on core nodes |
| **EMR Serverless** | 4 workers × 4 vCPU × 16 GB on demand | ~$0.14 | No idle cluster, scales per-stage |
| **EKS on Fargate** | Same workers | ~$0.15 | Plus EKS cluster fee - only justified if multi-tenant |

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
