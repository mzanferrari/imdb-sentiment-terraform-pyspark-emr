# Security groups for the EMR cluster.
#
# Design choice: no inbound SSH. Operator access goes through AWS Session
# Manager (encrypted, IAM-authenticated, audited via CloudTrail).
# See docs/ARCHITECTURE.md "Network and security groups".

# ─── MASTER NODE ──────────────────────────────────────────────────────────────
# No inbound; all outbound (S3, ECR, package mirrors).

resource "aws_security_group" "main_security_group" {
  name        = "${var.project_name}-emr-main-sg"
  description = "EMR master node - outbound only, accessed via SSM"

  revoke_rules_on_delete = true

  egress {
    description = "All outbound (needed for S3, ECR, package mirrors)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-emr-main-sg"
  })
}

# ─── CORE NODES ───────────────────────────────────────────────────────────────
# Intra-cluster traffic plus all outbound.
#
# Self-referencing ingress lets master and core nodes talk freely on every
# port without exposing them externally.

resource "aws_security_group" "core_security_group" {
  name        = "${var.project_name}-emr-core-sg"
  description = "EMR core nodes - intra-cluster ingress, all outbound"

  revoke_rules_on_delete = true

  ingress {
    description = "Intra-SG traffic on all ports"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-emr-core-sg"
  })
}
