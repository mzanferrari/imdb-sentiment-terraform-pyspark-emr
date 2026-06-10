# Project bucket holding raw data, pipeline scripts, output models, and logs.
# SSM Parameter Store entries make the bucket layout discoverable to the
# pipeline at runtime without hardcoding paths.

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

# ─── BUCKET ───────────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "create_bucket" {
  bucket        = "${var.project_name}-${var.project_id}"
  force_destroy = var.force_destroy

  tags = merge(var.common_tags, {
    Name    = "${var.project_name}-app-bucket"
    Purpose = "Pipeline scripts, raw data, ML outputs, logs"
  })
}

# ─── VERSIONING ───────────────────────────────────────────────────────────────
# Recovery from accidental overwrites of pipeline scripts.

resource "aws_s3_bucket_versioning" "versioning_bucket" {
  bucket = aws_s3_bucket.create_bucket.id

  versioning_configuration {
    status = var.versioning_bucket
  }

  depends_on = [aws_s3_bucket.create_bucket]
}

# ─── PUBLIC ACCESS LOCKDOWN ───────────────────────────────────────────────────
#
# block_public_policy and restrict_public_buckets are kept true. EMR does NOT
# require a public bucket policy - it accesses S3 via the EC2 instance profile
# role, which is private IAM access.

resource "aws_s3_bucket_public_access_block" "emr_bucket_access_block" {
  bucket = aws_s3_bucket.create_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ─── SSM PARAMETER STORE ──────────────────────────────────────────────────────
# Control plane for runtime configuration.
#
# The Python pipeline reads these parameters at startup (see
# src/pipeline/config.py). Names must match the suffixes that config.py
# requests: bucket_name, s3/path_raw_data, s3/path_output, s3/path_logs.

resource "aws_ssm_parameter" "bucket_name" {
  name  = "/${var.project_name}/bucket_name"
  type  = "String"
  value = aws_s3_bucket.create_bucket.id
  tags  = var.common_tags
}

resource "aws_ssm_parameter" "path_raw_data" {
  name  = "/${var.project_name}/s3/path_raw_data"
  type  = "String"
  value = "s3://${var.project_name}-${var.project_id}/dados/"
  tags  = var.common_tags
}

resource "aws_ssm_parameter" "path_output" {
  name  = "/${var.project_name}/s3/path_output"
  type  = "String"
  value = "s3://${var.project_name}-${var.project_id}/output/"
  tags  = var.common_tags
}

resource "aws_ssm_parameter" "path_logs" {
  name  = "/${var.project_name}/s3/path_logs"
  type  = "String"
  value = "s3://${var.project_name}-${var.project_id}/logs/"
  tags  = var.common_tags
}

# ─── UPLOAD ARTIFACTS TO BUCKET ───────────────────────────────────────────────
# Pipeline code, raw data, bootstrap scripts, and the built pipeline.zip.

module "s3_objects" {
  source = "./s3_objects"

  project_name = var.project_name
  project_id   = var.project_id
  files_bucket = var.files_bucket
  files_data   = var.files_data
  files_bash   = var.files_bash
  files_build  = var.files_build

  depends_on = [aws_s3_bucket.create_bucket]
}
