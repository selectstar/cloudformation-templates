#!/bin/bash
set -eux
BUCKET="${1-cf-templates-pp3cips1o7jf-us-east-2}"
PREFIX="${2-aurora}"

# Upload files
sha512sum ./SelectStarAurora.json
aws s3 cp ./SelectStarAurora.json "s3://$BUCKET/$PREFIX/" --acl public-read
