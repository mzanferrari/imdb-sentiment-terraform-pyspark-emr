output "cluster_id" {
  value       = aws_emr_cluster.cluster.id
  description = "ID of the provisioned EMR cluster (changes per apply)"
}

output "cluster_name" {
  value       = aws_emr_cluster.cluster.name
  description = "Name of the cluster"
}
