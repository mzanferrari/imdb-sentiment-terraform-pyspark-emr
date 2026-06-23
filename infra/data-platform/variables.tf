variable "region" {
  type        = string
  description = "AWS region. Default eu-west-1 (Ireland) - see docs/adrs/0002-aws-region.md"
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

variable "terraform_user" {
  type        = string
  description = "IAM username for legacy state-access policy. Empty for SSO (default); the permission set provides state access. See ADR 0007."
  default     = ""
}

variable "versioning_bucket" {
  type        = string
  description = "Bucket versioning state - Enabled or Suspended"
  default     = "Enabled"

  validation {
    condition     = contains(["Enabled", "Suspended"], var.versioning_bucket)
    error_message = "versioning_bucket must be Enabled or Suspended."
  }
}

variable "environment" {
  type        = string
  description = "Deployment environment label (dev | staging | prod)"
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "files_bucket" {
  type        = string
  description = "Local path with Python scripts to upload to S3"
  default     = "../../src/pipeline"
}

variable "files_data" {
  type        = string
  description = "Local path with the dataset to upload to S3"
  default     = "../../data"
}

variable "files_bash" {
  type        = string
  description = "Local path with bash scripts to upload to S3"
  default     = "../../scripts"
}

variable "files_build" {
  type        = string
  description = "Local path with the built pipeline.zip (from make package)"
  default     = "../../build"
}

variable "s3_force_destroy" {
  type        = bool
  description = "If true, `terraform destroy` empties the bucket before deleting it. DEV ONLY."
  default     = false
}

variable "alert_email" {
  type        = string
  description = "Email for cost alerts. Set in terraform.tfvars (gitignored), not here."
  default     = ""

  validation {
    condition     = var.alert_email == "" || can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.alert_email))
    error_message = "alert_email must be empty (no subscription) or a valid email address."
  }
}

variable "monthly_budget_usd" {
  type        = string
  description = "Monthly budget ceiling in USD for the cost alarm"
  default     = "10"
}

# ─── EMR SIZING ───────────────────────────────────────────────────────────────
# See docs/adrs/0003-emr-deployment-mode.md
variable "emr_master_instance_type" {
  type        = string
  description = "EC2 instance type for the EMR master node (Graviton/ARM; min xlarge - EMR rejects *.large)"
  default     = "m7g.xlarge"
}

variable "emr_core_instance_type" {
  type        = string
  description = "EC2 instance type for EMR core nodes (Graviton/ARM; min xlarge - EMR rejects *.large)"
  default     = "m7g.xlarge"
}

variable "emr_core_instance_count" {
  type        = number
  description = "Number of EMR core nodes"
  default     = 1

  validation {
    condition     = var.emr_core_instance_count >= 1
    error_message = "Need at least 1 core node."
  }
}

variable "emr_core_bid_price" {
  type        = string
  description = "Spot bid price for core nodes (USD/h). Empty string = On-Demand. Set to m7g.xlarge On-Demand as ceiling so Spot always allocates."
  default     = "0.164"
}

variable "emr_idle_timeout_seconds" {
  type        = number
  description = "Auto-terminate cluster after this many seconds of idle time"
  default     = 600
}
