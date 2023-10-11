#!/bin/bash
set -eux
BUCKET="${1-cf-templates-pp3cips1o7jf-us-east-2}"
PREFIX="${2-rds-for-postgresql}"

# Upload files
sha512sum ./SelectStarRDS.json
aws s3 cp ./SelectStarRDS.json "s3://$BUCKET/$PREFIX/" --acl public-read
