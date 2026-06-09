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
  description = "IAM username that runs Terraform (for state bucket access policy)"
}

variable "common_tags" {
  type        = map(string)
  description = "Tags applied to all resources for cost allocation"
}

variable "region" {
  type        = string
  description = "AWS region, used to scope SSM parameter ARNs in the least-privilege policy"
}
