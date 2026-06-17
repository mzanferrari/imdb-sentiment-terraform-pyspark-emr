# ADR 0007 - SSO-Compatible State Access (terraform_user optional)

- **Status:** Accepted
- **Date:** 2026-06-17
- **Deciders:** mzanferrari

## Context

The project's security posture, stated in the README, is "IAM Identity Center (SSO) for humans, Instance Profiles + STS for workloads, zero access keys by design". The `terraform_state_access` resource in `modules/iam` contradicted that posture: it attached an inline policy to an IAM user (`aws_iam_user_policy`, keyed by `var.terraform_user`), which only works when Terraform runs under a long-lived IAM user with access keys - exactly the model the README argues against.

Running Terraform under an SSO session (the recommended path) authenticates as an assumed role, not an IAM user, so the resource fails: there is no IAM user to attach the policy to. The variable was also required (no default), forcing every deployment to supply an IAM username even when running under SSO.

This surfaced during a real end-to-end deployment under an SSO profile, where `terraform plan` could not satisfy `aws_iam_user_policy.terraform_state_access`.

## Decision

Make the state-access policy conditional and the variable optional.

- `var.terraform_user` defaults to `""` at both declaration sites (root and `modules/iam`).
- `aws_iam_user_policy.terraform_state_access` gets `count = var.terraform_user != "" ? 1 : 0`: it is created only when an IAM username is explicitly provided.
- Under SSO (the default, `terraform_user = ""`), the resource is skipped. State-bucket access comes from the permission set the SSO session already carries (broad enough S3 access to read and write the remote state), so no per-user policy is needed.
- Under a legacy IAM-user workflow, setting `terraform_user` to a username restores the original behaviour unchanged.

The resource is referenced nowhere else (no output, no other resource depends on it), so the `count` introduces no downstream `[0]` indexing elsewhere.

## Consequences

- The default path now matches the README: deploy under SSO, no IAM user, no access keys. The code stops contradicting the stated posture.
- The IAM-user path is preserved for anyone who genuinely runs that way - the change is additive, not a removal.
- State access under SSO relies on the permission set rather than a narrow per-user policy. This is broader than the original least-privilege policy, which scoped access to exactly the state file and its lockfile. For a foundational human-access control this is an accepted trade-off; tightening the permission set to a per-action custom policy is tracked separately and would restore the narrow scope at the permission-set layer instead of via an IAM-user policy.
- The example tfvars documents both modes so a new user understands the choice rather than copying an IAM-user value blindly.

## Revisit when

The permission set is tightened to a custom per-action policy (the narrow state-access scope moves there), or the project standardises on a single auth model and the other path can be dropped.
