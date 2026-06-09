variable "project_name" {
  type        = string
  description = "Project namespace"
}

variable "project_id" {
  type        = string
  description = "AWS Account ID"
}

variable "files_bucket" {
  type        = string
  description = "Local path with pipeline scripts (.py files)"
}

variable "files_data" {
  type        = string
  description = "Local path with the dataset.csv to upload"
}

variable "files_bash" {
  type        = string
  description = "Local path with bash scripts (bootstrap_emr.sh)"
}

variable "files_build" {
  type        = string
  description = "Local path holding the built pipeline.zip (from make package)"
}
