import json
import sys

BUCKET = sys.argv[1]
KEY = sys.argv[2]

with open('SelectStarRedshift.json', 'r') as f:
    data = json.load(f)
with open('SelectStarRedshift.json', 'w') as f:
    for key in ["LambdaProvisionFunction", 'LambdaTransformFunction']:
        data["Resources"][key]["Properties"]["Code"] = {
            "S3Bucket": BUCKET,
            "S3Key": KEY,
        }
    json.dump(data, f, indent=4,)
