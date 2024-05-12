#!/bin/bash
set -eux
BUCKET="${1-cf-templates-pp3cips1o7jf-us-east-2}"
PREFIX="${2-quicksight}"

# Upload files
aws s3 cp ./SelectStarQuickSight.json "s3://$BUCKET/$PREFIX/" --acl public-read
