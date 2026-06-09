variable "project_name" {
  type        = string
  description = "Short project namespace"
}

variable "project_id" {
  type        = string
  description = "AWS Account ID"
}

variable "region" {
  type        = string
  description = "AWS region (propagated as Spark env var)"
}

variable "instance_profile" {
  type        = string
  description = "ARN of the IAM Instance Profile for EC2 nodes"
}

variable "service_role" {
  type        = string
  description = "ARN of the IAM Service Role for the EMR cluster"
}

variable "master_instance_type" {
  type        = string
  description = "EC2 type for the master node"
}

variable "core_instance_type" {
  type        = string
  description = "EC2 type for core nodes"
}

variable "core_instance_count" {
  type        = number
  description = "Number of core nodes"
}

variable "core_bid_price" {
  type        = string
  description = "Spot bid price for core nodes (USD/h). Empty string = On-Demand."
}

variable "idle_timeout_seconds" {
  type        = number
  description = "Idle timeout in seconds before auto-termination"
}

variable "common_tags" {
  type        = map(string)
  description = "Tags applied to all resources for cost allocation"
}

variable "cost_alerts_topic_arn" {
  type        = string
  description = "SNS topic ARN to notify when the cluster sits idle"
}
