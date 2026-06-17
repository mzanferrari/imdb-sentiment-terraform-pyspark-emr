variable "project_name" {
  type        = string
  description = "Project namespace"
}

variable "project_id" {
  type        = string
  description = "AWS Account ID"
}

variable "terraform_user" {
  type        = string
  description = "IAM username for legacy state-access policy. Empty for SSO (default); the permission set provides state access. See ADR 0007."
  default     = ""
}

variable "common_tags" {
  type        = map(string)
  description = "Tags applied to all resources for cost allocation"
}

variable "region" {
  type        = string
  description = "AWS region, used to scope SSM parameter ARNs in the least-privilege policy"
}
