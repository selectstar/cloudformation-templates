#!/bin/bash
set -eux
BUCKET="${1-cf-templates-pp3cips1o7jf-us-east-2}"
PREFIX="${2-mysql}"

# Upload files
aws s3 cp ./SelectStarMySQL.json "s3://$BUCKET/$PREFIX/" --acl public-read
