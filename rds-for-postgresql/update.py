import json
import sys

BUCKET = sys.argv[1]
KEY = sys.argv[2]

with open("SelectStarRDS.json", "r") as f:
    data = json.load(f)

with open("SelectStarRDS.json", "w") as f:
    data["Resources"]["LambdaFunction"]["Properties"]["Code"] = {
        "S3Bucket": BUCKET,
        "S3Key": KEY,
    }
    json.dump(
        data,
        f,
        indent=4,
    )
