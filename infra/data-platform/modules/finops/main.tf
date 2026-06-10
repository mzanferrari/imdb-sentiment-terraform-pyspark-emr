# FinOps - budget alarm and alert topic.
#
# Account-level monthly budget with SNS notification. The topic is created
# empty: subscribe an email after apply (kept out of code to avoid putting a
# personal address in a public repo). This closes the STATUS.md TODO and gives
# a slow reactive backstop. The fast detector (idle cluster) lives in the emr
# module, which has the cluster id needed for the CloudWatch dimension.

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

# ─── SNS TOPIC AND EMAIL SUBSCRIPTION ────────────────────────────────────────

resource "aws_sns_topic" "cost_alerts" {
  name = "${var.project_name}-cost-alerts"
  tags = var.common_tags
}

# Optional email subscription. Created only when alert_email is non-empty, so
# the address stays in terraform.tfvars (gitignored), never in versioned code.
# count keeps the module usable with no email (topic-only) for CI/plan runs.
resource "aws_sns_topic_subscription" "cost_alerts_email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.cost_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ─── MONTHLY BUDGET ───────────────────────────────────────────────────────────

resource "aws_budgets_budget" "monthly" {
  name         = "${var.project_name}-monthly"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Alert at 80% (forecast) and 100% (actual). Forecast catches a runaway
  # trend before the money is fully spent; actual is the hard backstop.
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_sns_topic_arns = [aws_sns_topic.cost_alerts.arn]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.cost_alerts.arn]
  }
}
