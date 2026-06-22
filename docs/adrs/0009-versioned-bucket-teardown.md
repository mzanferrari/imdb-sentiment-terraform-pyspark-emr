# ADR 0009 - Two-Step Teardown for Versioned Buckets

- **Status:** Accepted
- **Date:** 2026-06-22
- **Deciders:** mzanferrari

## Context

Both S3 buckets in this project have versioning enabled: the state bucket (bootstrap stack), which holds the Terraform remote state, and the project bucket (data-platform stack), which holds pipeline data. Versioning on the state bucket is deliberate - it is a safety net, so a corrupted or accidentally overwritten state can be recovered from a prior version.

A versioned bucket cannot be deleted while it still holds object versions or delete markers. Neither `aws s3 rb --force` nor Terraform's `force_destroy` removes historical versions - both operate only on current objects. As a result, `terraform destroy` fails with `BucketNotEmpty` on a versioned bucket that has any version history.

This surfaced during the validated redeploys: `make destroy` left the state bucket orphaned, and it had to be emptied by version ID manually before the bootstrap stack could be torn down. The original `make destroy` also masked the failure with `|| true`, so the error was invisible until the orphaned bucket was noticed afterward.

The state bucket intentionally has no `force_destroy` set. That absence is a design signal - "stop and think before deleting this" - because the state bucket is the infrastructure's source of truth. A teardown that force-empties it automatically would override that signal. The project bucket is different: its data is reproducible (re-running the pipeline regenerates it), so emptying it on teardown costs nothing.

## Decision

Split teardown into two targets that treat each bucket according to its nature, backed by a shared purge script.

- `scripts/empty_versioned_bucket.sh` purges all object versions and delete markers from a named bucket. It is idempotent and safe on a missing bucket.
- `make destroy` empties the project bucket automatically (reproducible data) and destroys the data-platform stack, then reports that the state bucket is preserved and how to remove it.
- `make destroy-state` is a separate target with its own confirmation prompt. It empties and destroys the versioned state bucket - the deliberate act that honours the bucket's absent `force_destroy`.

The `|| true` that masked destroy failures was removed from the Terraform destroy steps, so a real failure now surfaces. It is kept only on the purge-script call, where failing on an already-absent bucket is safe.

## Consequences

- Teardown is two conscious steps. Removing the application (`make destroy`) is routine; removing the foundation (`make destroy-state`) is a separate, separately-confirmed act. This matches the difference in value between reproducible pipeline data and the state that is the source of truth.
- The knowledge that versioned buckets need an explicit purge is now encoded in the script and documented in DEPLOYMENT Step 8, rather than living only in operator memory.
- A user who runs only `make destroy` leaves the state bucket (and a few cents of versioned storage) in place until they deliberately remove it. This is the intended trade-off: safety over one-command convenience.
- `force_destroy` on the project bucket remains parametrized (default false). The teardown path no longer depends on it being true, since the purge script handles versions regardless.

## Revisit when

The project moves to a managed-state backend that handles its own lifecycle (for example Terraform Cloud or Spacelift), at which point the bootstrap state bucket and its bespoke teardown would no longer exist; or AWS changes S3 so that `force_destroy` removes versions, which would let a single `terraform destroy` handle versioned buckets directly.
