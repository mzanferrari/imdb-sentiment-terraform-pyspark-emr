output "cost_alerts_topic_arn" {
  value       = aws_sns_topic.cost_alerts.arn
  description = "SNS topic ARN for cost alerts - subscribe an email after apply"
}
