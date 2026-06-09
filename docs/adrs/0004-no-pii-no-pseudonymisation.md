# ADR 0004 - Data Privacy: No PII in This Dataset, GDPR-Aware Design Notes

- **Status:** Accepted
- **Date:** 2026-05-19
- **Deciders:** mzanferrari

## Context

The project processes the public IMDB movie reviews dataset (~50k reviews, labeled positive/negative). Reviews are anonymized at source - no usernames, no identifiers tied to natural persons. The `sentiment` label is a derived class, not a personal attribute.

GDPR/LGPD do not apply to this specific data because it contains no personal data as defined in Article 4 GDPR.

However, the **architecture pattern** (S3 + EMR + Spark + ML training) is the same that a real EU client would use for PII-laden workloads (customer reviews on e-commerce, social listening, support tickets). A portfolio that ignores this misses an opportunity to signal GDPR awareness.

## Decision

**This project:** Continue using the public IMDB dataset. **No PII processing**. No pseudonymisation pipeline implemented for this dataset.

**Demonstrative notes:** Document explicitly in this ADR how the design would change if the data contained PII. This makes GDPR awareness visible without overengineering the current scope.

## Rationale

### What changes if data contains PII

The same pipeline carrying real customer reviews (with usernames, IPs, account IDs, possibly review content referring to other persons) would need:

#### Discovery phase additions

- **Legal basis** must be declared. For customer reviews on own platform: typically Article 6(1)(b) (performance of contract) or 6(1)(f) (legitimate interest, with LIA documented). For ML training over reviews: legitimate interest typically requires balancing test and opt-out mechanism.
- **Data Protection Impact Assessment (DPIA)** triggered if profiling, large scale, or special category data (Article 35).
- **Retention policy** declared per data category - raw reviews, derived features, model artifacts may have different timelines.

#### Architecture additions

- **Ingestion-time pseudonymisation.** Personal identifiers (user_id, IP, email) replaced with stable tokens at ingestion. Token-to-identity vault stored separately, with stricter access controls (separate AWS account or KMS key).
- **Column-level classification.** Iceberg properties or Glue Data Catalog tags marking `pii: true`, `sensitivity: confidential` per column. Downstream tools (dbt, Spark) read these to enforce masking.
- **Encryption.**
  - At rest: KMS-CMK (not AWS-managed key) so deletion of the key effectively renders backups unreadable.
  - In transit: TLS 1.2+ for all S3 access (enforced via bucket policy `aws:SecureTransport`).
- **Logging without PII.** Application logs must not include raw review text or user identifiers in plain form. Log forwarders strip or hash before persisting.
- **Access controls.**
  - IAM roles per data tier: `data-engineer-raw`, `data-engineer-curated`, `analyst-mart` - least privilege.
  - Lake Formation or Unity Catalog (if Databricks) for fine-grained access on `pii: true` columns.
  - Audit logs on access (CloudTrail data events for S3).
- **Data Subject Rights pipelines.**
  - **DSAR (right of access, Article 15).** Pipeline accepting an identifier, returning all data about the subject across raw, curated, mart, and model training sets, formatted for delivery to the subject within 30 days.
  - **Right to erasure (Article 17).** Pipeline accepting an identifier, performing deletion across all derived datasets (including re-training the model on a dataset minus the subject's contributions, if the legal basis was consent). Audit log of erasure execution.
  - **Right to portability (Article 20).** Export of the subject's raw contributions in machine-readable format.
- **Transfer mechanisms.** Any cross-border transfer (e.g., EU -> US for support tooling) requires Standard Contractual Clauses or adequacy decision. Schrems II implications for US transfers must be considered case by case.

#### Operational additions

- **Quarterly audit** of access logs vs documented access patterns.
- **Penetration testing** for the data platform's exposed endpoints.
- **Incident response plan** with 72-hour notification window per Article 33 GDPR.

### Why not implement all this in the current project

Implementing the full GDPR pipeline against a dataset that contains no PII would be:

1. **Inauthentic** - the controls would protect nothing real.
2. **Misleading** - a real client looking at the repo could mistake "pseudonymisation working on `sentiment` labels" for production-grade pseudonymisation. The two are not equivalent.
3. **Time-displacing** - the same effort spent on the H2 domain shift (Comex) produces more portfolio value.

The honest signal is: "I know what would change. I chose not to fake it on a dataset that doesn't need it. Here's the design I would propose."

## Consequences

**Accepted:**

- Recruiters who only skim won't see PII handling code in this repo. The ADR exists to be discovered on inspection.

**Mitigation:**

- README briefly notes "GDPR-aware design - see ADR-0004" with link.
- If a future iteration of the project shifts to a domain with PII (e.g., synthetic e-commerce reviews), this ADR is revisited and a real pseudonymisation pipeline is implemented.

## Revisit Criteria

- If the dataset is replaced with one containing PII, implement the controls described above and mark this ADR as **Superseded**.
- If the project is forked for real client work, this ADR becomes the design baseline and is operationalized.
- Reassess against EU AI Act timeline if the project starts producing ML models classified as high-risk under the Act.
