import json
import sys

BUCKET = sys.argv[1]
KEY = sys.argv[2]

with open("SelectStarRDS.json", "r") as f:
    data = json.load(f)

with open("SelectStarRDS.json", "w") as f, open("copy_handler.py", "r") as f_copy:
    data["Resources"]["LambdaCopyFunction"]["Properties"]["Code"] = {
        "ZipFile": f_copy.read(),
    }
    data["Resources"]["LambdaCopy"]["Properties"]["srcBucket"] = BUCKET
    data["Resources"]["LambdaCopy"]["Properties"]["srcKey"] = KEY

    json.dump(
        data,
        f,
        indent=4,
    )
