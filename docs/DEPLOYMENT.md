# Deployment Guide

End-to-end procedure to bring this project from clone to running EMR job and back to zero AWS spend.

---

## Pre-flight checklist

Before running anything that touches AWS:

- [ ] AWS account with billing alerts configured (see "Budget alarm" below)
- [ ] AWS CLI configured (`aws configure` or `aws sso login`)
- [ ] Verify region: `aws configure get region` (project default is `eu-west-1`)
- [ ] EC2 Spot service-linked role exists (one-time per account): `aws iam create-service-linked-role --aws-service-name spot.amazonaws.com` (returns an "already exists" error if present - that is fine). The core nodes use Spot, which requires this account-level role.
- [ ] Verify identity: `aws sts get-caller-identity`
- [ ] IAM permissions for: `s3:*`, `ec2:*` (for EMR), `elasticmapreduce:*`, `iam:CreateRole` + `iam:PutRolePolicy`, `ssm:PutParameter` + `ssm:GetParameter`
- [ ] Terraform 1.15+ installed (`terraform version`)
- [ ] Python 3.11 installed, not 3.12 (`python --version`) - PySpark 3.5 needs `distutils`
- [ ] `uv` installed (`uv --version`) - optional but recommended
- [ ] Docker (optional) installed (`docker --version`)

---

## Step 1 - Clone and configure

```bash
git clone https://github.com/mzanferrari/imdb-sentiment-terraform-pyspark-emr.git
cd imdb-sentiment-terraform-pyspark-emr

# Initialize Python environment
make install

# Install pre-commit hooks
pre-commit install
```

Copy the template tfvars files and fill in **your** values:

```bash
cp infra/bootstrap/terraform.tfvars.example       infra/bootstrap/terraform.tfvars
cp infra/data-platform/terraform.tfvars.example   infra/data-platform/terraform.tfvars
```

Required fields in both files:

```hcl
region            = "eu-west-1"
project_name      = "mz-p2"
project_id        = "<YOUR_AWS_ACCOUNT_ID>"
versioning_bucket = "Enabled"
```

Additional field for data-platform (leave empty for SSO, the recommended path):

```hcl
terraform_user = ""   # SSO: leave empty. Legacy IAM-user auth: set your username.
```

These `.tfvars` files are gitignored. They will **never** be committed. Keep them on your machine.

---

## Step 2 - Cost alerts

The monthly budget alarm is provisioned by Terraform (`modules/finops`). To receive notifications, set `alert_email` in your gitignored `terraform.tfvars` before applying the data-platform stack; Terraform creates the SNS subscription and AWS sends a one-time confirmation link. No manual budget setup is needed. An invalid address fails at `terraform plan`, before any resource is created.

---

## Step 3 - Download the dataset

```bash
make ingest
```

This runs `scripts/ingest_data.py`. It is idempotent: re-running does nothing if the file exists and the SHA256 matches.

Verify:

```bash
ls -lh data/dataset.csv
# Expect ~63 MB
```

---

## Step 4 - Bootstrap (creates Terraform state bucket)

```bash
make bootstrap
```

Equivalent to:

```bash
cd infra/bootstrap
terraform init
terraform plan
terraform apply
```

Expected output: a single S3 bucket named `<project>-terraform-<account_id>` and a generated file `infra/data-platform/scripts/backend.conf`.

**One-time per environment.** You don't run this on every deploy.

---

## Step 5 - Deploy the data-platform stack

```bash
make data-platform
```

Equivalent to:

The bootstrap stage already generated `scripts/backend.conf` (it holds your state bucket name and is gitignored). Just initialize against it:

```bash
cd infra/data-platform
terraform init -backend-config=scripts/backend.conf
terraform plan
terraform apply
```

This creates:

- The project's S3 bucket (`<project>-<account_id>`)
- IAM roles for EMR service and EC2 instances
- SSM parameters with bucket and path information
- EMR cluster (release 7.13.0, Spark 3.5)
- Security groups
- The cluster will run its 2 steps and **auto-terminate**

Expected runtime: 8-15 minutes from `apply` to cluster termination.

---

## Step 6 - Monitor execution

Open the AWS Console:

1. **EMR -> Clusters** - see the cluster status (Starting -> Bootstrapping -> Running -> Terminated)
2. **EMR -> Cluster -> Steps** - see each step transition through Pending -> Running -> Completed
3. **CloudWatch Logs** - application logs streamed from the cluster

From the CLI:

```bash
CLUSTER_ID=$(cd infra/data-platform && terraform output -raw emr_cluster_id)

aws emr describe-cluster --cluster-id "$CLUSTER_ID" \
  --query 'Cluster.Status.State'

aws emr list-steps --cluster-id "$CLUSTER_ID" \
  --query 'Steps[].{Name:Name,State:Status.State}'
```

### Watching a run in real time

Three ways, simplest to most detailed.

**Poll the step status** - no extra tooling, refreshing every 15s:

```bash
CLUSTER_ID=$(cd infra/data-platform && terraform output -raw emr_cluster_id)
watch -n 15 "aws emr list-steps --cluster-id $CLUSTER_ID \
  --query 'Steps[].{Name:Name,State:Status.State}' --output table"
```

**Read the pipeline logs from S3** - a few minutes' delay, since EMR syncs periodically. The Spark step's stdout holds the model accuracies:

```bash
BUCKET=$(cd infra/data-platform && terraform output -raw bucket_name)
aws s3 ls "s3://$BUCKET/logs/$CLUSTER_ID/steps/" --recursive
# copy and gunzip the stdout.gz of the Spark step
```

**Open a shell on the master node** - true real-time, needs the Session Manager plugin:

```bash
MASTER=$(aws emr list-instances --cluster-id $CLUSTER_ID \
  --instance-group-types MASTER --query 'Instances[0].Ec2InstanceId' --output text)
aws ssm start-session --target "$MASTER"
# inside: tail -f /var/log/hadoop-yarn/...
```

The first two need only the AWS CLI; the shell option needs the Session Manager plugin (a one-time install, see the AWS docs).

---

## Step 7 - Verify outputs

After cluster termination:

```bash
BUCKET=$(aws ssm get-parameter --name /mz-p2/bucket_name --query 'Parameter.Value' --output text)

# Featurized datasets (Parquet, partitioned by label)
aws s3 ls s3://$BUCKET/data/HTFfeaturizedData/   --recursive | head
aws s3 ls s3://$BUCKET/data/TFIDFfeaturizedData/ --recursive | head
aws s3 ls s3://$BUCKET/data/W2VfeaturizedData/   --recursive | head

# Trained models
aws s3 ls s3://$BUCKET/output/ --recursive

# Application logs
aws s3 cp s3://$BUCKET/logs/ ./logs-local/ --recursive
```

---

## Step 8 - Teardown

Teardown is two deliberate steps, one per bucket type.

```bash
make destroy
```

Asks for confirmation, empties the app bucket (pipeline data is reproducible), and destroys the data-platform stack. The Terraform state bucket is left intact - it is versioned as a safety net and is not force-destroyed.

To remove the state bucket as well (a separate, deliberate act):

```bash
make destroy-state
```

This has its own confirmation and empties the versioned bucket before destroying it. Run it only after the data-platform stack is already gone.

Why two steps: a versioned bucket cannot be deleted while it holds object versions, and neither `aws s3 rb --force` nor Terraform `force_destroy` removes historical versions - only an explicit purge does. The app bucket is emptied automatically because its data is reproducible; the state bucket, your source of truth, is kept until you remove it on purpose.

Manual equivalent, without the Make targets:

```bash
scripts/empty_versioned_bucket.sh "$(cd infra/data-platform && terraform output -raw bucket_name)"
cd infra/data-platform && terraform destroy
# later, to remove the state bucket too:
scripts/empty_versioned_bucket.sh "$(cd infra/bootstrap && terraform output -raw state_bucket_name)"
cd infra/bootstrap && terraform destroy
```

After this, your AWS account is back to zero project-related resources. Verify in the Billing console after 24 hours that no charges continue to accrue.

---

## Docker-based workflow (alternative)

If you don't want to install Terraform and AWS CLI on the host:

```bash
docker compose up -d
docker compose exec mz-p2 bash

# Inside the container:
make deploy
```

The container has Terraform 1.15.5, AWS CLI v2, and Python pre-installed. AWS credentials are read from `~/.aws/` on the host (mounted into the container) - they are never baked into the image.

---

## Common issues

### `Error: ParameterNotFound: /mz-p2/s3/path_output`

The SSM parameters are created by the s3 module of the data-platform stack. If the parameter does not exist, the data-platform stack did not finish applying. Run `terraform apply` again and look for errors during the s3 module section.

### `BOOTSTRAP_FAILURE` on the cluster

The EMR bootstrap script (`scripts/bootstrap_emr.sh`) failed on at least one node. Inspect:

```bash
aws s3 ls s3://$BUCKET/logs/$CLUSTER_ID/node/

# Then download the failing node's setup log
aws s3 cp s3://$BUCKET/logs/$CLUSTER_ID/node/<instance-id>/setup-devel.gz - | gunzip
```

Common causes:

- Network egress blocked (check security group rules and NACLs)
- `pip install` rate-limited from PyPI (mitigate by pinning a mirror)

### `Spot interruption` aborted the job

Core nodes on Spot can be reclaimed by AWS at any time. Spark generally retries, but if a late-stage shuffle fails the whole job may abort. Options:

- Increase `bid_price` closer to On-Demand rate (defeats the purpose)
- Move master + small core fleet to On-Demand, keep task nodes on Spot
- Migrate to EMR Serverless (no Spot, predictable pricing) - see ADR-0003

### `Error: Backend initialization required`

You changed `backend.conf` or moved the state bucket. Run:

```bash
cd infra/data-platform
terraform init -reconfigure -backend-config=scripts/backend.conf
```

### Cluster keeps running indefinitely

A step failed with `action_on_failure = "CONTINUE"`, the cluster is waiting for the next step (which doesn't exist), and `keep_job_flow_alive_when_no_steps` is `false` - it should terminate. If it doesn't:

```bash
aws emr terminate-clusters --cluster-ids $CLUSTER_ID
```

And open an issue against this project documenting the symptom.

---

## Cost guardrails to keep on

In order of priority:

1. **Budget alarm** at $10/month (Step 2).
2. **`auto_termination_policy`** with `idle_timeout = 600`. Configured in `modules/emr/main.tf`.
3. **`make destroy`** after every test run unless you're actively iterating.
4. **Tags applied uniformly** (planned in H1 closing) to enable Cost Allocation Reports.
5. **Cost Explorer dashboard** with filter `Tag:Project = mz-p2` to track spend over time.
