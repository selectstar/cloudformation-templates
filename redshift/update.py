import json

with open('SelectStarRedshift.json', 'r') as f:
    data = json.load(f)
with open('SelectStarRedshift.json', 'w') as f, open('provision.py', 'r') as script_fp:
    data['Resources']['LambdaFunction']['Properties']['Code']['ZipFile'] = script_fp.read()
    json.dump(data, f, indent=4,)
