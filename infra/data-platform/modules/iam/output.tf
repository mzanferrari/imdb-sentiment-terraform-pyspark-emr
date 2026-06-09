output "service_role" {
  value       = aws_iam_role.iam_emr_service_role.arn
  description = "ARN of the EMR Service Role (control plane)"
}

output "instance_profile" {
  value       = aws_iam_instance_profile.emr_profile.arn
  description = "ARN of the EC2 Instance Profile (Spark workers)"
}
