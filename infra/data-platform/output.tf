output "emr_cluster_id" {
  value       = module.emr.cluster_id
  description = "ID of the provisioned EMR cluster (changes per apply)"
}

output "bucket_name" {
  value       = "${var.project_name}-${var.project_id}"
  description = "Name of the project S3 bucket"
}

output "cost_alerts_topic_arn" {
  value       = module.finops.cost_alerts_topic_arn
  description = "Subscribe an email to this SNS topic to receive cost alerts"
}
