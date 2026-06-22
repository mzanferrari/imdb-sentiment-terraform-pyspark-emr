#!/bin/bash
#
# Empty a versioned S3 bucket so it can be destroyed.
#
# Deletes every object version and delete marker from a bucket, which is the
# prerequisite for removing a versioned bucket. Used by `make destroy` (app
# bucket) and `make destroy-state` (state bucket).
#
# Why this exists:
# - A versioned bucket cannot be deleted while it holds object versions. Neither
#   `aws s3 rb --force` nor Terraform `force_destroy` removes historical
#   versions, so `terraform destroy` fails with BucketNotEmpty until the
#   versions and delete markers are purged. This script does that purge.
#
# Notes:
# - Idempotent: re-running on an emptied bucket is safe (purges nothing).
# - Safe on a missing bucket: exits 0 with a notice, so teardown is not blocked
#   when the bucket was already removed.
# - Fails fast (set -euo pipefail) so callers see a non-zero exit on real errors.
# - Requires jq (present on the AMI image and in the dev container).

set -euo pipefail

BUCKET="${1:-}"
if [ -z "${BUCKET}" ]; then
    echo "Usage: $0 <bucket-name>" >&2
    exit 1
fi

# Bucket may already be gone (teardown re-run). Treat as success.
if ! aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
    echo "Bucket ${BUCKET} does not exist or is not accessible - nothing to empty."
    exit 0
fi

echo "Emptying versioned bucket: ${BUCKET}"

# ─── OBJECT VERSIONS ──────────────────────────────────────────────────────────
versions=$(aws s3api list-object-versions --bucket "${BUCKET}" \
    --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
    --output json)
if [ "$(echo "${versions}" | jq -r '.Objects | length')" -gt 0 ]; then
    aws s3api delete-objects --bucket "${BUCKET}" --delete "${versions}" >/dev/null
    echo "Deleted object versions"
else
    echo "No object versions to delete"
fi

# ─── DELETE MARKERS ───────────────────────────────────────────────────────────
markers=$(aws s3api list-object-versions --bucket "${BUCKET}" \
    --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' \
    --output json)
if [ "$(echo "${markers}" | jq -r '.Objects | length')" -gt 0 ]; then
    aws s3api delete-objects --bucket "${BUCKET}" --delete "${markers}" >/dev/null
    echo "Deleted delete markers"
else
    echo "No delete markers to delete"
fi

echo "Bucket ${BUCKET} is now empty"
