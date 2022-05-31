import json

with open('SelectStarRDS.json', 'r') as f:
    data = json.load(f)

with open('SelectStarRDS.json', 'w') as f, open('provision.py', 'r') as script_fp:
    data['Resources']['LambdaFunction']['Properties']['Code']['ZipFile'] = script_fp.read()
    json.dump(data, f, indent=4,)
