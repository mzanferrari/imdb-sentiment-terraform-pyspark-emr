# ADR 0002 - AWS Region: eu-west-1 (Ireland)

- **Status:** Accepted
- **Date:** 2026-05-19
- **Deciders:** mzanferrari

## Context

The project is positioned as a portfolio piece for EU-remote Data Engineering roles. Region choice signals data residency awareness and influences cost, latency, and feature availability.

## Decision

Default region: **`eu-west-1`** (Dublin, Ireland).

Override mechanism: `var.region` in `terraform.tfvars`.

## Rationale

| Region | Code | Pricing tier | EMR availability | Notes |
|---|---|---|---|---|
| Ireland | `eu-west-1` | Cheapest EU tier | Full | Mature region, all services |
| London | `eu-west-2` | Mid | Full | Post-Brexit data residency concern for some EU customers |
| Frankfurt | `eu-central-1` | Mid-High | Full | Preferred for DACH and finance |
| Paris | `eu-west-3` | Mid | Full | Preferred for FR clients |
| Stockholm | `eu-north-1` | Cheapest tier | Limited features | Best for nordics, green energy narrative |
| Madrid | `eu-south-2` | Mid | Limited | Newer region |

**Why Ireland:**

1. **Cost.** `eu-west-1` is the cheapest fully-featured EU region. For a portfolio incurring real charges, this matters.
2. **Maturity.** All services GA. No surprises with missing instance types or regional bugs.
3. **EU data residency.** Inside EEA. Adequate for GDPR compliance for personal data of EU residents (Schrems II considerations apply for transfers outside EEA, not relevant here).
4. **Career narrative.** Several large EU data platforms (Stripe, Klarna, Spotify, Booking.com, Zalando) have significant presence in `eu-west-1`. Familiarity matters.

**Why not Frankfurt:**

Frankfurt is the default choice for DACH-targeting projects, but is ~15% more expensive than Ireland for EMR. For a portfolio project where DACH-specific clients aren't yet identified, the cost difference doesn't justify.

**Why not US regions:**

Project explicitly targets EU-remote roles. Hosting in `us-east-1` for cost (it is cheaper than `eu-west-1`) contradicts the narrative. Coherence beats marginal savings here.

## Consequences

**Accepted:**

- Data and compute fully within EEA - GDPR posture clear by default.
- Slight latency increase for any access from non-EU sources (negligible for batch).
- All AMIs, AZ topology, support availability assume Ireland.

**Trade-offs documented:**

- If a future client mandates Frankfurt or Paris, the override mechanism makes this a 1-line change. The IaC is region-agnostic by design.

## Revisit Criteria

- Adopt `eu-central-1` if a real client is DACH-based.
- Adopt `eu-north-1` if "green compute" becomes a narrative requirement (Stockholm runs on near-100% renewable energy).
- Move out of `eu-west-1` if AWS pricing in the region drops below par with newer EU regions (unlikely short-term).
