variable "region" {
  type        = string
  description = "AWS region (default eu-west-1, see docs/adrs/0002-aws-region.md)"
  default     = "eu-west-1"
}

variable "project_name" {
  type        = string
  description = "Short project namespace (lowercase, dash-separated)"
}

variable "project_id" {
  type        = string
  description = "AWS Account ID (12 digits)"

  validation {
    condition     = can(regex("^[0-9]{12}$", var.project_id))
    error_message = "project_id must be a 12-digit AWS Account ID."
  }
}

variable "versioning_bucket" {
  type        = string
  description = "Bucket versioning state - Enabled or Suspended. Always Enabled in real environments."
  default     = "Enabled"

  validation {
    condition     = contains(["Enabled", "Suspended"], var.versioning_bucket)
    error_message = "versioning_bucket must be Enabled or Suspended."
  }
}

variable "common_tags" {
  type        = map(string)
  description = "Tags applied to all resources created by this stack"
  default = {
    Project    = "imdb-sentiment-terraform-pyspark-emr"
    Stack      = "bootstrap"
    ManagedBy  = "terraform"
    CostCenter = "portfolio"
  }
}
