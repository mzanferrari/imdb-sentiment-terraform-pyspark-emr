# Uploads from local filesystem to the project S3 bucket.
#
# Three categories:
#   - pipeline/: Python source files (main.py, config.py, etc.)
#   - pipeline/pipeline.zip: built artifact, uploaded separately from build/
#   - dados/:    raw dataset (dataset.csv from scripts/ingest_data.py)
#   - scripts/:  shell scripts (bootstrap_emr.sh runs on every EMR node)
#
# fileset() is recursive (**) and re-evaluated on each `terraform plan`.
# etag = filemd5() forces a re-upload when local content changes.

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

# ─── PYTHON PIPELINE MODULES (.PY ONLY) ───────────────────────────────────────
#
# Filter to .py only - the built pipeline.zip is uploaded by a dedicated
# resource below, reading from build/. This keeps IDE caches and __pycache__
# out of the bucket.

resource "aws_s3_object" "python_scripts" {
  for_each = toset([
    for f in fileset(var.files_bucket, "**") :
    f if can(regex("\\.py$", f))
  ])

  bucket = "${var.project_name}-${var.project_id}"
  key    = "pipeline/${each.value}"
  source = "${var.files_bucket}/${each.value}"
  etag   = filemd5("${var.files_bucket}/${each.value}")
}

# ─── PIPELINE.ZIP (BUILT ARTIFACT FROM MAKE PACKAGE) ──────────────────────────
#
# Uploaded from build/, not from src/pipeline/. The filemd5() is a gate:
# terraform plan fails if the zip was not built, forcing make package before
# deploy instead of failing at runtime on the cluster.

resource "aws_s3_object" "pipeline_zip" {
  bucket = "${var.project_name}-${var.project_id}"
  key    = "pipeline/pipeline.zip"
  source = "${var.files_build}/pipeline.zip"
  etag   = filemd5("${var.files_build}/pipeline.zip")
}

# ─── RAW DATASET ──────────────────────────────────────────────────────────────

resource "aws_s3_object" "raw_data" {
  for_each = toset([
    for f in fileset(var.files_data, "**") :
    f if can(regex("\\.csv$", f))
  ])

  bucket = "${var.project_name}-${var.project_id}"
  key    = "dados/${each.value}"
  source = "${var.files_data}/${each.value}"
  etag   = filemd5("${var.files_data}/${each.value}")
}

# ─── BASH SCRIPTS (EMR BOOTSTRAP) ─────────────────────────────────────────────

resource "aws_s3_object" "bash_scripts" {
  for_each = toset([
    for f in fileset(var.files_bash, "**") :
    f if can(regex("\\.sh$", f))
  ])

  bucket = "${var.project_name}-${var.project_id}"
  key    = "scripts/${each.value}"
  source = "${var.files_bash}/${each.value}"
  etag   = filemd5("${var.files_bash}/${each.value}")
}

# ─── EMPTY PREFIXES (FOLDERS) FOR OUTPUTS AND LOGS ────────────────────────────
#
# S3 has no real folders - these create zero-byte objects with trailing slash
# so AWS Console shows the prefixes before the pipeline writes content.

resource "aws_s3_object" "output_prefix" {
  bucket = "${var.project_name}-${var.project_id}"
  key    = "output/"
}

resource "aws_s3_object" "logs_prefix" {
  bucket = "${var.project_name}-${var.project_id}"
  key    = "logs/"
}
