# Terraform and provider versions for the data-platform stack.
#
# Backend "s3" stores remote state in the bucket created by the bootstrap stack.
# The actual region/bucket/key values come from `scripts/backend.conf`, written
# by the bootstrap stack and consumed via:
#   terraform init -backend-config=scripts/backend.conf

terraform {
  required_version = "~> 1.15"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    encrypt      = true
    use_lockfile = true
    # region, bucket, and key are populated by backend.conf at init time.
  }
}

provider "aws" {
  region = var.region
}
