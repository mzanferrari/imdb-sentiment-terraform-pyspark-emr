# ADR 0008 - Custom EMR Service-Role Policy

- **Status:** Accepted
- **Date:** 2026-06-19
- **Deciders:** mzanferrari

## Context

The EMR service role (`iam_emr_service_role`) is assumed by Amazon EMR to provision the cluster - it launches the EC2 instances, creates network interfaces, and tidies them up when the cluster terminates. It was attached to the AWS managed policy `AmazonEMRServicePolicy_v2`.

`AmazonEMRServicePolicy_v2` is tag-scoped: it grants `ec2:RunInstances` (and the related network actions) only on subnets and security groups carrying the tag `for-use-with-amazon-emr-managed-policies = true`. Amazon EMR auto-tags security groups it creates and propagates the tag to resources it provisions, but resources it does not create - notably subnets - must be tagged manually.

This project runs in the account's default VPC and does not manage networking: it specifies no subnet, letting EMR place the cluster in a default subnet. That default subnet is not tagged, so the service role could not launch instances in it. The cluster reached provisioning and then terminated with `TERMINATED_WITH_ERRORS: insufficient EC2 permissions`. This surfaced only during a real end-to-end deployment, after earlier blockers were cleared - no prior deploy had reached instance provisioning.

Satisfying the v2 policy would mean managing networking the project deliberately avoids: either tagging a subnet the project does not own (fragile, environment-dependent) or creating and tagging a dedicated VPC and subnet (roughly 50 to 100 lines of networking for an ephemeral, auto-terminating cluster). Both are disproportionate to the use case.

## Decision

Replace the `AmazonEMRServicePolicy_v2` attachment with a custom inline policy on the service role, granting the EC2 lifecycle actions EMR needs without the subnet-tag condition.

The policy covers: instance provisioning and termination (`RunInstances`, `TerminateInstances`, fleets, launch templates), network interfaces, security-group rule management, EBS volumes, `ec2:Describe*`, and Spot request actions. It includes the cleanup actions explicitly - the AWS docs warn that a service role without them leaves billable orphaned resources when the cluster ends.

`iam:PassRole` is scoped to the EC2 instance-profile role ARN with an `iam:PassedToService = ec2.amazonaws.com` condition, so the service role can hand the instance profile to the cluster's EC2 instances without the broad `PassRole *` that the v1 managed policy was criticised for.

## Consequences

- The cluster provisions in the default VPC without managing subnets or VPC tagging. Networking stays out of the project's scope, consistent with its proportionality stance.
- The service role's EC2 actions use `Resource = "*"` rather than the tag-scoped resources of the v2 policy. This is broader than the managed policy on the resource dimension, but scoped on the action dimension (only the lifecycle actions EMR uses, not `ec2:*`) and far narrower than attaching `AmazonEC2FullAccess`. The trade-off is accepted for an ephemeral single-cluster project.
- The policy is now owned and visible in the repo rather than referenced as an opaque managed ARN - easier to audit and reason about.
- If the project later manages its own VPC and subnets (for example to add VPC endpoints), tagging them and returning to the managed v2 policy becomes an option worth revisiting.

## Revisit when

The project starts managing its own networking (VPC, subnets, endpoints), at which point tagging the network chain and using the managed `AmazonEMRServicePolicy_v2` would restore AWS-maintained permissions; or AWS revises the v2 policy to not require subnet tags.
