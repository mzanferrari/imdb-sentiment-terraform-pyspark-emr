# Results

Validation of the deployed pipeline on AWS. The published repository was deployed from a clean clone, ran end to end on an ephemeral EMR cluster, and torn down - three times, independently, to confirm reproducibility.

## Model performance

Sentiment classification on 50,000 IMDB reviews (balanced: 25,000 positive, 25,000 negative). Three text-featurization strategies, each fed to Logistic Regression with cross-validation.

| Featurization | Classifier | Accuracy |
|---|---|---|
| Word2Vec | Logistic Regression | 87.07% |
| HashingTF | Logistic Regression | 72.34% |
| TF-IDF | Logistic Regression | 72.34% |

Word2Vec leads by a wide margin because it encodes semantic similarity - words with related meaning sit close in vector space - while HashingTF and TF-IDF are bag-of-words representations that ignore word relationships and tie exactly.

Results were bit-for-bit identical across three independent cluster runs (87.06534071948208 and 72.33531335513582), confirming the pipeline is deterministic: fixed random seed, explicit ordering, and a version-pinned runtime.

## Infrastructure

Amazon EMR 7.13 on Graviton (ARM) m7g.xlarge - master On-Demand, one core node on Spot. Cluster is ephemeral and self-terminating on idle.

| Metric | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Provisioning (create to ready) | 4m16s | 4m14s | 5m13s |
| Pipeline execution (Spark step) | 7m32s | 7m44s | 7m56s |
| Total cluster lifetime | 13m06s | 12m59s | 14m39s |
| Normalized instance hours | 16 | 16 | 16 |

Timing is consistent across runs: provisioning 4 to 5 minutes, pipeline around 7.5 to 8 minutes, cluster auto-terminating near 13 minutes total.

## Cost per run

A full pipeline run (cluster provisioning through auto-termination, roughly 13 minutes) costs about **$0.074**, measured in AWS Cost Explorer across two runs on 2026-06-19 and divided by two.

| Component | Cost per run |
|---|---|
| EC2 instances (master On-Demand + core Spot) | $0.0536 |
| EMR uplift | $0.0117 |
| EBS volumes | $0.0050 |
| VPC | $0.0022 |
| S3 (storage + requests) | $0.0020 |
| **Total** | **$0.074** |

Cost is kept low by design: Graviton instances (cheaper than x86 equivalents), Spot pricing on the core node, a single right-sized core, and auto-termination that prevents idle spend. The cluster bills per second from launch to termination, so a 13-minute run incurs roughly 13 minutes of charges, not an hourly minimum.

## What this validates

- The published repository deploys clean from a fresh clone (ten merged pull requests)
- The pipeline runs end to end: ingestion, cleaning, three featurizations, three cross-validated models, all persisted to S3
- Output is deterministic and reproducible across independent infrastructure
- Cost is controlled by an ephemeral, Spot-priced, auto-terminating Graviton cluster - a full ML run for roughly seven cents

## Reproducing these results

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the full deploy and teardown procedure. In short: configure AWS access, deploy the bootstrap and data-platform stacks, let the cluster run the pipeline, and tear down. Model artifacts and featurized datasets land in the project S3 bucket under `output/` and `data/`.
