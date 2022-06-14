import provision
import os

CLUSTER = "postgres-test-data"


class MockContext(object):
    def __init__(self):
        self.log_stream_name = "test-stream"


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
            "secretArn": "arn:aws:secretsmanager:us-east-2:792169733636:secret:stack-integration/selectstar-user-credentials-bnZWSD",
            "ServerName": CLUSTER,
            "Schema": ["*.*"],
            "DbUser": "postgres",
            "DbPassword": os.environ['PG_PASSWORD'],
            "Region": "us-east-2",
            "ConfigureLogging": "true",
            "ConfigureLoggingRestart": "true",
        },
    }


if __name__ == "__main__":
    server = "postgres-test-data"
    configureLogging = True
    configureLoggingRestart = True
    provision.ensure_valid_cluster_engine(server)
    provision.ensure_custom_parameter_group(server, configureLogging)
    provision.ensure_parameter_set(server, configureLogging, "log_statement", "all")
    provision.ensure_parameter_set(server, configureLogging, "log_min_duration_statement", "0")
    provision.ensure_log_exporting_enabled(server, configureLogging)
    provision.ensure_instance_restarted(server, configureLoggingRestart)
    provision.handler(get_event("Create"), MockContext())
    provision.handler(get_event("Delete"), MockContext())
