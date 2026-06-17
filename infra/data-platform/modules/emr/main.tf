# EMR cluster definition.
#
# Changes vs the original course-derived version:
#   - Single Spark-submit step (the original had a duplicate step that called
#     main.py without the bucket argument, guaranteed to fail).
#   - auto_termination_policy added - kills idle clusters before they burn budget.
#   - Instance types are variables, not hardcoded.
#   - Common tags applied for cost allocation.
#   - Pipeline modules packaged as pipeline.zip uploaded by Terraform; spark-submit
#     references it via --py-files.

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

# ─── EMR CLUSTER ──────────────────────────────────────────────────────────────

resource "aws_emr_cluster" "cluster" {
  name          = "${var.project_name}-emr-${var.project_id}"
  release_label = "emr-7.13.0"
  applications  = ["Hadoop", "Spark"]

  termination_protection            = false
  keep_job_flow_alive_when_no_steps = false

  log_uri      = "s3://${var.project_name}-${var.project_id}/logs/"
  service_role = var.service_role

  ec2_attributes {
    instance_profile                  = var.instance_profile
    emr_managed_master_security_group = aws_security_group.main_security_group.id
    emr_managed_slave_security_group  = aws_security_group.core_security_group.id
  }

  master_instance_group {
    instance_type = var.master_instance_type
  }

  core_instance_group {
    instance_type  = var.core_instance_type
    instance_count = var.core_instance_count
    bid_price      = var.core_bid_price != "" ? var.core_bid_price : null
  }

  auto_termination_policy {
    idle_timeout = var.idle_timeout_seconds
  }

  bootstrap_action {
    name = "Install Python packages"
    path = "s3://${var.project_name}-${var.project_id}/scripts/bootstrap_emr.sh"
  }

  # Steps run sequentially. Action_on_failure controls behavior:
  #   - TERMINATE_CLUSTER: hard stop; useful for pre-flight setup
  #   - CONTINUE: log the failure but keep going (cluster eventually idles out)
  step {
    name              = "Sync pipeline scripts from S3"
    action_on_failure = "TERMINATE_CLUSTER"

    hadoop_jar_step {
      jar = "command-runner.jar"
      args = [
        "aws", "s3", "cp",
        "s3://${var.project_name}-${var.project_id}/pipeline/",
        "/home/hadoop/pipeline/",
        "--recursive",
      ]
    }
  }

  step {
    name              = "Run Spark sentiment pipeline"
    action_on_failure = "CONTINUE"

    hadoop_jar_step {
      jar = "command-runner.jar"
      args = [
        "spark-submit",
        "--py-files", "/home/hadoop/pipeline/pipeline.zip",
        "/home/hadoop/pipeline/main.py",
        "${var.project_name}-${var.project_id}",
        var.project_name,
      ]
    }
  }

  configurations_json = jsonencode([
    {
      Classification = "spark-env"
      Configurations = [
        {
          Classification = "export"
          Properties = {
            AWS_DEFAULT_REGION = var.region
            EXECUTION_ENV      = "emr"
            PYSPARK_PYTHON     = "/usr/bin/python3.11"
          }
        }
      ]
    },
    {
      Classification = "spark-defaults"
      Properties = {
        "spark.pyspark.python"             = "/usr/bin/python3.11"
        "spark.pyspark.driver.python"      = "/usr/bin/python3.11"
        "spark.dynamicAllocation.enabled"  = "true"
        "spark.network.timeout"            = "800s"
        "spark.executor.heartbeatInterval" = "60s"
      }
    }
  ])

  # for-use-with-amazon-emr-managed-policies: required by AmazonEMRFullAccessPolicy_v2.
  # The v2 managed policy is tag-scoped - RunJobFlow is denied without this tag. EMR
  # propagates it to resources it creates; SGs we create ourselves carry it explicitly.
  tags = merge(var.common_tags, {
    Name                                       = "${var.project_name}-emr-cluster"
    "for-use-with-amazon-emr-managed-policies" = "true"
  })
}

# ─── COST GUARD - ALARM ON IDLE CLUSTER ───────────────────────────────────────
#
# auto_termination_policy already kills an idle cluster after idle_timeout.
# This alarm is the second layer: if auto-terminate ever fails, IsIdle staying
# at 1 for 15 minutes fires an alert via SNS. EMR publishes IsIdle (0/1) every
# 5 minutes, so 3 periods = 15 min of confirmed idle before alerting.

resource "aws_cloudwatch_metric_alarm" "cluster_idle" {
  alarm_name          = "${var.project_name}-emr-idle-${var.project_id}"
  namespace           = "AWS/ElasticMapReduce"
  metric_name         = "IsIdle"
  dimensions          = { JobFlowId = aws_emr_cluster.cluster.id }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 3
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_description   = "EMR cluster idle 15 min - auto-termination may have failed"
  alarm_actions       = [var.cost_alerts_topic_arn]
  treat_missing_data  = "notBreaching"
  tags                = var.common_tags
}
