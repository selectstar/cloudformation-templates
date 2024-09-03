import json
import sys

BUCKET = sys.argv[1]
KEY = sys.argv[2]

with open("SelectStarDAS.json", "r") as f:
    data = json.load(f)
with open("SelectStarDAS.json", "w") as f, open("copy_handler.py", "r") as f_copy:
    data["Resources"]["LambdaCopyFunction"]["Properties"]["Code"] = {
        "ZipFile": f_copy.read(),
    }
    data["Resources"]["LambdaCopy"]["Properties"]["srcBucket"] = BUCKET
    data["Resources"]["LambdaCopy"]["Properties"]["srcKey"] = KEY
    data["Resources"]["LambdaExecutionRole"]["Properties"]["Policies"][0][
        "PolicyDocument"
    ]["Statement"][0]["Resource"] = f"arn:aws:s3:::{BUCKET}/{KEY}"
    json.dump(
        data,
        f,
        indent=4,
    )
