# Data Platform - main composition module.
#
# Two-stage IaC: this stack assumes the bootstrap stack has already created the
# remote state bucket (see infra/bootstrap/).

# ─── COMMON TAGS APPLIED TO EVERY RESOURCE THAT SUPPORTS TAGGING ──────────────
locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Repository  = "github.com/mzanferrari/imdb-sentiment-terraform-pyspark-emr"
    CostCenter  = "portfolio"
  }
}

# ─── STORAGE + SSM PARAMETER STORE ────────────────────────────────────────────
module "s3" {
  source = "./modules/s3"

  project_name      = var.project_name
  project_id        = var.project_id
  versioning_bucket = var.versioning_bucket
  files_bucket      = var.files_bucket
  files_data        = var.files_data
  files_bash        = var.files_bash
  files_build       = var.files_build
  force_destroy     = var.s3_force_destroy
  common_tags       = local.common_tags
}

# ─── IAM - ROLES FOR EMR SERVICE AND EC2 INSTANCE PROFILE ─────────────────────
module "iam" {
  source = "./modules/iam"

  project_name   = var.project_name
  project_id     = var.project_id
  region         = var.region
  terraform_user = var.terraform_user
  common_tags    = local.common_tags
}

# ─── EMR - COMPUTE CLUSTER ────────────────────────────────────────────────────
module "emr" {
  source = "./modules/emr"

  project_name     = var.project_name
  project_id       = var.project_id
  region           = var.region
  instance_profile = module.iam.instance_profile
  service_role     = module.iam.service_role
  common_tags      = local.common_tags

  master_instance_type = var.emr_master_instance_type
  core_instance_type   = var.emr_core_instance_type
  core_instance_count  = var.emr_core_instance_count
  core_bid_price       = var.emr_core_bid_price
  idle_timeout_seconds = var.emr_idle_timeout_seconds

  cost_alerts_topic_arn = module.finops.cost_alerts_topic_arn
}

# ─── FINOPS - BUDGET ALARM AND ALERT TOPIC ────────────────────────────────────
module "finops" {
  source = "./modules/finops"

  project_name       = var.project_name
  alert_email        = var.alert_email
  monthly_budget_usd = var.monthly_budget_usd
  common_tags        = local.common_tags
}
