#/bin/bash
set -eux;
( find . -name 'SelectStar*.json'; find . -name 'SelectStar*.yaml'; )  | while read FILE; do
    aws cloudformation validate-template --template-body "file://${FILE}"
done;
