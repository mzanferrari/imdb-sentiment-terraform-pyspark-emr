variable "project_name" {
  type        = string
  description = "Project namespace, used to name budget and topic"
}

variable "alert_email" {
  type        = string
  description = "Email subscribed to cost alerts. Empty skips the subscription (set it in terraform.tfvars, never in code)."
  default     = ""
}

variable "monthly_budget_usd" {
  type        = string
  description = "Monthly budget ceiling in USD (string, AWS budgets API expects it)"
  default     = "10"
}

variable "common_tags" {
  type        = map(string)
  description = "Tags applied to the SNS topic"
}
