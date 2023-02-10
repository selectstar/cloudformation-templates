#!/bin/bash
set -eux
BUCKET="${1-cf-templates-pp3cips1o7jf-us-east-2}"
PREFIX="${2-glue}"

# Upload files
aws s3 cp ./SelectStarGlue.json "s3://$BUCKET/$PREFIX/" --acl public-read
