#!/bin/bash
set -eux
BUCKET="${1-cf-templates-pp3cips1o7jf-us-east-2}"
PREFIX="${2-aurora-postgresql}"

# Upload files
sha512sum ./SelectStarAuroraPostgreSQL.json
aws s3 cp ./SelectStarAuroraPostgreSQL.json "s3://$BUCKET/$PREFIX/" --acl public-read
