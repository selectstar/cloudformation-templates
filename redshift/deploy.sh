#!/bin/bash
set -eux
BUCKET="${1-cf-templates-pp3cips1o7jf-us-east-2}"
PREFIX="${2-redshift}"

# Generate templates
python update.py
# Upload files
sha512sum ./SelectStarRedshift.json
aws s3 cp ./SelectStarRedshift.json "s3://$BUCKET/$PREFIX/" --acl public-read
