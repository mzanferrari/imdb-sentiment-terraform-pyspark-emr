# Bootstrap stack: creates the S3 bucket that holds the remote state of the
# data-platform stack, plus a generated `backend.conf` consumed by the
# data-platform's `terraform init -backend-config=...`.
#
# Why two stacks: avoids the chicken-and-egg of "where does the state of the
# state bucket live". This stack uses local state (small, easy to rebuild via
# `terraform import` if lost).

# ─── STATE BUCKET ─────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "terraform_state" {
  bucket = "${var.project_name}-terraform-${var.project_id}"

  # State bucket must never be deleted accidentally - there is no recovery for
  # a destroyed state bucket holding real infrastructure references.
  force_destroy = false

  tags = merge(var.common_tags, {
    Name    = "${var.project_name}-terraform-state"
    Purpose = "Terraform remote state for data-platform stack"
  })
}

# ─── VERSIONING ───────────────────────────────────────────────────────────────
# Allows recovery from accidental state corruption.

resource "aws_s3_bucket_versioning" "state_versioning" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = var.versioning_bucket
  }

  depends_on = [aws_s3_bucket.terraform_state]
}

# ─── SERVER-SIDE ENCRYPTION ───────────────────────────────────────────────────
#
# AES256 is sufficient for a portfolio. Production setups typically use
# SSE-KMS with a customer-managed key (CMK) so deletion of the key
# effectively cryptoshreds backups.

resource "aws_s3_bucket_server_side_encryption_configuration" "state_encryption" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ─── PUBLIC ACCESS LOCKDOWN ───────────────────────────────────────────────────
# State buckets must never be public.

resource "aws_s3_bucket_public_access_block" "state_block" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ─── GENERATED BACKEND.CONF CONSUMED BY THE DATA-PLATFORM STACK ───────────────
#
# Path is relative to the bootstrap directory. The data-platform stack reads
# this file via `terraform init -backend-config=scripts/backend.conf`.

resource "local_file" "backend_conf" {
  filename = "${path.module}/../data-platform/scripts/backend.conf"

  content = <<-EOT
    region = "${aws_s3_bucket.terraform_state.region}"
    bucket = "${aws_s3_bucket.terraform_state.id}"
    key    = "data-platform.tfstate"
  EOT

  depends_on = [aws_s3_bucket.terraform_state]
}

# ─── OUTPUTS ──────────────────────────────────────────────────────────────────

output "state_bucket_name" {
  value       = aws_s3_bucket.terraform_state.id
  description = "Name of the S3 bucket holding the remote state for data-platform"
}

output "state_bucket_arn" {
  value       = aws_s3_bucket.terraform_state.arn
  description = "ARN of the state bucket"
}
