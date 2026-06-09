# Terraform and provider versions for the bootstrap stack.
# The bootstrap stack creates the S3 bucket that will hold the remote state
# of the data-platform stack - its own state stays local (small, easy to
# recreate via `terraform import` if lost).

terraform {
  required_version = "~> 1.14"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }

    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.region
}
