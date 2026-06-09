variable "project_name" {
  type        = string
  description = "Project namespace"
}

variable "project_id" {
  type        = string
  description = "AWS Account ID"
}

variable "versioning_bucket" {
  type        = string
  description = "Bucket versioning state - Enabled or Suspended"
}

variable "files_bucket" {
  type        = string
  description = "Local path holding Python pipeline modules to upload to S3"
}

variable "files_data" {
  type        = string
  description = "Local path holding the dataset to upload to S3"
}

variable "files_bash" {
  type        = string
  description = "Local path holding bash scripts (EMR bootstrap) to upload to S3"
}

variable "files_build" {
  type        = string
  description = "Local path holding the built pipeline.zip"
}

variable "force_destroy" {
  type        = bool
  description = "If true, `terraform destroy` empties the bucket before deleting. DEV ONLY."
}

variable "common_tags" {
  type        = map(string)
  description = "Tags applied to all resources for cost allocation"
}
