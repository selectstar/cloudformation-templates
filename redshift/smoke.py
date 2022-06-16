import provision
import logging

CLUSTER = "redshift-cluster-1"
class MockContext(object):
    def __init__(self):
        self.log_stream_name = 'test-stream'

def get_event(request_type):
    return {
    "RequestType": request_type,
    "ServiceToken": "arn:aws:lambda:us-east-2:123456789012:function:lambda-error-processor-primer-14ROR2T3JKU66",
    "ResponseURL": "http://httpbin.org/put",
    "StackId": "arn:aws:cloudformation:us-east-2:123456789012:stack/lambda-error-processor/1134083a-2608-1e91-9897-022501a2c456",
    "RequestId": "5d478078-13e9-baf0-464a-7ef285ecc786",
    "LogicalResourceId": "primerinvoke",
    "ResourceType": "AWS::CloudFormation::CustomResource",
    "ResourceProperties": {
        "ServiceToken": "arn:aws:lambda:us-east-2:123456789012:function:lambda-error-processor-primer-14ROR2T3JKU66",
        "RedshiftRole": "arn:aws:iam::792169733636:role/aws-service-role/redshift.amazonaws.com/AWSServiceRoleForRedshift",
        "Bucket": "redshift-logging-selectstar",
        "Cluster": CLUSTER,
        "Db": "dev",
        "Grant": ["*"],
        "DbUser": "awsuser",
        "Region": "us-east-2",
        "ConfigureS3Logging": "true",
        "ConfigureS3LoggingRestart": "true",
    },
}

if __name__ == '__main__':
    provision.ensure_custom_parameter_group(CLUSTER, True)
    provision.ensure_user_activity_enabled(CLUSTER, True)
    provision.ensure_cluster_restarted(CLUSTER, True)
    provision.handler(get_event("Create"), MockContext())
    provision.handler(get_event("Delete"), MockContext())
