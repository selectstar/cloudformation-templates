#!/bin/bash
set -eux
BUCKET="${1-cf-templates-pp3cips1o7jf-us-east-2}"
PREFIX="${2-das}"

pip install poetry # ensure that poetry is installed

# Convert YAML to JSON
cat ./SelectStarDAS.yaml |  yq e -o=json > ./SelectStarDAS.json

# Build deployment package
pushd das-firehose-log-process
poetry build --format wheel
poetry run pip install --upgrade --only-binary :all: --platform manylinux2014_aarch64 --python-version 3.12 --target package --implementation cp dist/*.whl
(cd package; zip -X --no-dir-entries --quiet --recurse-paths ../handler.zip .)
popd;

# Generate templates
python update.py "$BUCKET" "$PREFIX/deployment-package.zip"

# Upload files
aws s3 cp ./SelectStarDAS.json "s3://$BUCKET/$PREFIX/" --acl public-read
aws s3 cp ./das-firehose-log-process/handler.zip "s3://$BUCKET/$PREFIX/deployment-package.zip" --acl public-read
