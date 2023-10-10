#!/bin/bash
set -eux
BUCKET="${1-cf-templates-pp3cips1o7jf-us-east-2}"
PREFIX="${2-rds-for-postgresql}"

# Build deployment package
rm -f deployment-package.zip
pip3 install --target ./package -r requirements.txt
pushd package
zip -r ../deployment-package.zip .
zip -g ../deployment-package.zip ../provision.py
zip -g ../deployment-package.zip ../cfnresponse.py
popd;
# Generate templates
python3 update.py "$BUCKET" "$PREFIX/deployment-package.zip"
# Upload files
sha512sum ./SelectStarRDS.json ./deployment-package.zip
aws s3 cp ./SelectStarRDS.json "s3://$BUCKET/$PREFIX/" --acl public-read
aws s3 cp ./deployment-package.zip "s3://$BUCKET/$PREFIX/" --acl public-read
