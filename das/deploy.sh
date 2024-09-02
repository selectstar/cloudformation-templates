#!/bin/bash
set -eux
BUCKET="${1-cf-templates-pp3cips1o7jf-us-east-2}"
PREFIX="${2-das}"

# Convert YAML to JSON
cat ./SelectStarDAS.yaml |  yq e -j > ./SelectStarDAS.json

# Upload files
aws s3 cp ./SelectStarDAS.json "s3://$BUCKET/$PREFIX/" --acl public-read
aws s3 cp ./deployment-package.zip "s3://$BUCKET/$PREFIX/" --acl public-read
