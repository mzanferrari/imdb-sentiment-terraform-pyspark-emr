# ADR 0001 - IaC tool: Terraform over Pulumi/CDK

- **Status:** Accepted
- **Date:** 2026-05-19
- **Deciders:** mzanferrari

## Context

The project provisions an end-to-end AWS data platform (S3, IAM, EMR cluster, SSM parameters). The infrastructure must be:

- Reproducible across accounts and regions
- Declarative (drift-detectable)
- Reviewable in pull requests via `terraform plan`
- Lock-able for concurrent runs
- Familiar to most data platform engineers in the EU market

Candidates considered: Terraform, AWS CDK, Pulumi, CloudFormation, Crossplane.

## Decision

Use **Terraform 1.14+** with the AWS provider 6.x.

State stored remotely in S3 with native lockfile (Terraform 1.10+ feature, no DynamoDB lock table needed).

## Rationale

| Criterion | Terraform | CDK | Pulumi | CloudFormation |
|---|---|---|---|---|
| Multi-cloud portability | Yes - Native | No - AWS-only | Yes - Native | No - AWS-only |
| Job market familiarity (EU) | Yes - Dominant | Partial - Growing | Partial - Niche | Partial - Declining |
| HCL learning curve | Partial - Custom DSL | Yes - TypeScript/Python | Yes - Same | Partial - Verbose YAML/JSON |
| State management maturity | Yes - Mature | Yes - Via CloudFormation | Yes - Mature | Yes - Native |
| Module ecosystem | Yes - Largest | Partial - Growing | Partial - Growing | Partial - Limited |
| Native S3 state locking (no DynamoDB) | Yes - 1.10+ | N/A | N/A | N/A |

Terraform is the most widely-listed IaC tool in EU Data Engineering job descriptions in 2026, ahead of CDK and Pulumi by a wide margin. For a portfolio targeting EU roles, alignment with the market signal outweighs the language-of-choice argument for Pulumi/CDK.

## Consequences

**Accepted:**

- HCL is a custom DSL; team members fluent in Python/TypeScript only must learn it.
- Less expressive than Pulumi for complex programmatic infra.
- License is now BSL (Business Source License) post-IBM acquisition - not pure OSS but no impact for our use case.

**Mitigations:**

- Module discipline keeps complexity contained.
- For programmatic resources (e.g., generating policies from data), use `templatefile()` and `jsondecode()`.
- Track OpenTofu (fork of Terraform 1.5 under MPL) as fallback if license terms become problematic.

## Revisit Criteria

Re-evaluate when:

- Project requires >10 distinct AWS accounts orchestrated together (consider Pulumi or Crossplane for programmatic patterns)
- Team grows to >5 engineers with Python-only background and HCL becomes a bottleneck
- OpenTofu reaches feature parity and the EU market signal shifts
