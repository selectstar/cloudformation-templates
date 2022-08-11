#/bin/bash
set -eux;
find . -name 'SelectStar*.json' | while read FILE; do
    aws cloudformation validate-template --template-body "file://${FILE}"
done;
