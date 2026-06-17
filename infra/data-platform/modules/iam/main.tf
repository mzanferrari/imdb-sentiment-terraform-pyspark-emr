# IAM roles and policies.
#
# Two service roles + one optional user policy:
#   1. emr_service_role:  EMR control plane (provisioning the cluster)
#   2. emr_profile_role:  EC2 instances inside the cluster (Spark workers)
#   3. terraform user policy (optional): state-bucket access for legacy
#      IAM-user auth; skipped under SSO, where the permission set grants it
#
# Principle: no long-lived AWS access keys anywhere. Workloads assume their
# instance profile via the EC2 metadata service.

# ─── TERRAFORM REQUIREMENTS ───────────────────────────────────────────────────

terraform {
  required_version = "~> 1.15"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# ─── EMR SERVICE ROLE ─────────────────────────────────────────────────────────

resource "aws_iam_role" "iam_emr_service_role" {
  name = "${var.project_name}-emr-service-role"
  tags = var.common_tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = {
        Service = "elasticmapreduce.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "emr_service_role_policy" {
  role       = aws_iam_role.iam_emr_service_role.id
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEMRServicePolicy_v2"
}

# ─── EC2 INSTANCE PROFILE ROLE ────────────────────────────────────────────────
# Assumed by Spark workers via EC2 metadata.

resource "aws_iam_role" "iam_emr_profile_role" {
  name = "${var.project_name}-emr-profile-role"
  tags = var.common_tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

# SSM allows interactive shell access to EMR nodes via Session Manager
# (no SSH ports open, no public IP needed, audited via CloudTrail).
resource "aws_iam_role_policy_attachment" "ssm_policy" {
  role       = aws_iam_role.iam_emr_profile_role.id
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# ─── EC2 INSTANCE PROFILE - LEAST PRIVILEGE INLINE POLICY ─────────────────────
#
# Replaces the deprecated AWS-managed AmazonElasticMapReduceforEC2Role, which
# grants s3:*, dynamodb:*, sns:*, sqs:*, ec2:Describe*, rds:Describe* and more
# on Resource "*". AWS has put that policy on a deprecation path with no managed
# replacement and explicitly recommends a customer-managed least-privilege
# policy scoped to the resources the cluster actually uses.
# Ref: https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-iam-role-for-ec2.html
#
# Scope for this pipeline:
#   - read pipeline scripts + raw dataset, write features/models/logs in the
#     project bucket only (EMRFS read/write pattern from the AWS example)
#   - read the project SSM parameter subtree (runtime config)
#   - put CloudWatch metrics (EMR node monitoring) and archive step logs
# DynamoDB is intentionally omitted: EMRFS consistent view is not enabled.
# Glue is omitted: no Glue Data Catalog metastore in this project.

resource "aws_iam_role_policy" "emr_profile_least_privilege" {
  name = "${var.project_name}-emr-ec2-least-privilege"
  role = aws_iam_role.iam_emr_profile_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ProjectBucketReadWrite"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:GetBucketVersioning",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:ListBucketVersions",
          "s3:ListMultipartUploadParts",
          "s3:PutObject",
        ]
        Resource = [
          "arn:aws:s3:::${var.project_name}-${var.project_id}",
          "arn:aws:s3:::${var.project_name}-${var.project_id}/*",
        ]
      },
      {
        Sid    = "ProjectSsmReadConfig"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath",
        ]
        Resource = [
          "arn:aws:ssm:${var.region}:${var.project_id}:parameter/${var.project_name}",
          "arn:aws:ssm:${var.region}:${var.project_id}:parameter/${var.project_name}/*",
        ]
      },
      {
        Sid      = "CloudWatchNodeMetrics"
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData", "ec2:DescribeTags"]
        Resource = ["*"]
      },
    ]
  })
}

resource "aws_iam_instance_profile" "emr_profile" {
  name = "${var.project_name}-emr-profile"
  role = aws_iam_role.iam_emr_profile_role.name
  tags = var.common_tags
}

# ─── TERRAFORM USER POLICY (LEGACY IAM-USER AUTH ONLY) ────────────────────────
# Grants an IAM user access to the remote state bucket.
#
# Created only when var.terraform_user is set (legacy IAM-user workflow). Under
# the default SSO path (terraform_user = ""), this is skipped and state access
# comes from the permission set the assumed role already carries. See ADR 0007.

resource "aws_iam_user_policy" "terraform_state_access" {
  count = var.terraform_user != "" ? 1 : 0

  name = "${var.project_name}-terraform-state-access"
  user = var.terraform_user

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = "arn:aws:s3:::${var.project_name}-terraform-${var.project_id}"
      },
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject"]
        Resource = [
          "arn:aws:s3:::${var.project_name}-terraform-${var.project_id}/data-platform.tfstate",
        ]
      },
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = [
          "arn:aws:s3:::${var.project_name}-terraform-${var.project_id}/data-platform.tfstate.tflock",
        ]
      },
    ]
  })
}
