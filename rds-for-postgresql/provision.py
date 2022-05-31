import json
import boto3
import logging
import time
import urllib3
import cfnresponse
import botocore
import boto3

logging.basicConfig(
    format="%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M:%S",
    level=logging.INFO,
)

USER_ACTIVITY = "enable_user_activity_logging"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

rds_client = boto3.client("rds")
s3_client = boto3.client("s3")

class DataException(Exception):
    pass


def retry_aws(retries=3, codes=[]):
    def outer(fn):
        def inner(*args, **kwargs):
            error = None
            for i in range(0, retries):
                try:
                    return fn(*args, **kwargs)
                except botocore.exceptions.ClientError as err:
                    if err.response["Error"]["Code"] in codes:
                        error = err
                        time.sleep(2**i)
                        logger.warn(
                            f"API call failed ({err}); backing off and retrying..."
                        )
                    else:
                        raise err
            raise error

        return inner

    return outer


def ensure_valid_cluster_engine(server):
    instances = rds_client.describe_db_instances(DBInstanceIdentifier=server)[
        "DBInstances"
    ]
    if not instances:
        raise DataException(
            "Provisiong failed. DB instannce not found. Verify DB instance name."
        )
    instance = instances[0]
    if instance["Engine"] != "postgres":
        raise DataException(
            "Unsupported DB engine - required 'postgres'. Verify engine of DB instance."
        )
    if not instance["PubliclyAccessible"]:
        raise DataException(
            "Instance must be publicly available. Update the instance configurations and try again."
        )


def ensure_custom_parameter_group(server, configureLogging):
    instance = rds_client.describe_db_instances(DBInstanceIdentifier=server)[
        "DBInstances"
    ][0]
    enabled_custom_parameter = any(
        not group["DBParameterGroupName"].startswith("default.")
        for group in instance["DBParameterGroups"]
    )
    logging.info(
        "Determined DB instance parameter group. Enabled custom parameter group: %s",
        enabled_custom_parameter,
    )

    if enabled_custom_parameter:
        logging.info(
            "Custom parameter group set already. Nothing to do.",
        )
    elif configureLogging:
        paginator = rds_client.get_paginator("describe_db_engine_versions")
        family = next(
            (
                version["DBParameterGroupFamily"]
                for resp in paginator.paginate(
                    Engine=instance["Engine"],
                    EngineVersion=instance["EngineVersion"],
                )
                for version in resp["DBEngineVersions"]
            ),
            None,
        )
        if not family:
            raise Exception(
                "Configure logging failed."
                "Unable to determine db parameter group family for cluster."
            )
        parameter_group = f"custom-{server}"
        rds_client.create_db_parameter_group(
            Description="Created by Select Star via CloudFormation. Enables logging queries to CloudWatch.",
            DBParameterGroupName=parameter_group,
            DBParameterGroupFamily=family,
        )
        logging.info("A new parameter group created: %s", parameter_group)
        rds_client.modify_db_instance(
            DBInstanceIdentifier=server,
            ApplyImmediately=False,
            DBParameterGroupName=parameter_group,
        )
        logging.info(
            "DB instance '%s' updated. A new parameter group set: %s",
            server,
            parameter_group,
        )
        waiter = rds_client.get_waiter("db_instance_available")
        waiter.wait(DBInstanceIdentifier=server)
    else:
        raise DataException(
            "Configure logging failed."
            "Setup logging must be accepted in CloudFormation or custom parameter group set manually."
        )


def ensure_parameter_set(server, configureLogging, name, value):
    instance = rds_client.describe_db_instances(DBInstanceIdentifier=server)[
        "DBInstances"
    ][0]
    parameter_group = next(
        group["DBParameterGroupName"]
        for group in instance["DBParameterGroups"]
        if not group["DBParameterGroupName"].startswith("default.")
    )
    paginator = rds_client.get_paginator("describe_db_parameters")
    enabled_parameter = any(
        paginator.paginate(
            DBParameterGroupName=parameter_group,
            Filters=[{"Name": name, "Values": [value]}],
        )
    )
    if enabled_parameter:
        logging.info(
            "Parameter '%s' of parameter group '%s' already set to '%s'. Nothing to do.",
            name,
            parameter_group,
            value,
        )
    elif configureLogging:
        rds_client.modify_db_parameter_group(
            DBParameterGroupName=parameter_group,
            Parameters=[
                {
                    "ParameterName": name,
                    "ParameterValue": value,
                },
            ],
        )
        logging.info(
            "Parameter '%s' of parameter group '%s' update to '%s'. ",
            name,
            parameter_group,
            value,
        )
    else:
        raise DataException(
            "Configure logging failed."
            f"Setup logging must be accepted in CloudFormation or manually update parameter '{name}' of parameter group '{parameter_group}' to '{value}'."
        )


def ensure_log_exporting_enabled(server, configureLogging):
    instance = rds_client.describe_db_instances(DBInstanceIdentifier=server)[
        "DBInstances"
    ][0]
    enabled_log_export = instance.get("EnabledCloudwatchLogsExports", [])
    if "postgresql" in enabled_log_export:
        logging.info(
            "Log export configured. Nothing to do.",
        )
    elif configureLogging:
        rds_client.modify_db_instance(
            DBInstanceIdentifier=server,
            ApplyImmediately=False,
            CloudwatchLogsExportConfiguration={
                "EnableLogTypes": [
                    "postgresql",
                ],
            },
        )
        logging.info(
            "Exporting to CloudWatch enabling. Waiting to apply.",
        )
        waiter = rds_client.get_waiter("db_instance_available")
        waiter.wait(DBInstanceIdentifier=server)
        logging.info(
            "Exporting to CloudWatch applied.",
        )
    else:
        raise DataException(
            "Configure logging failed."
            f"Setup logging must be accepted in CloudFormation or exporting to CloudWatch enabled manually."
        )


def ensure_instance_restarted(server, configureLoggingRestart):
    instance = rds_client.describe_db_instances(DBInstanceIdentifier=server)[
        "DBInstances"
    ][0]
    pending_values = instance.get("PendingModifiedValues", {}).keys()
    pending_parameter_group = any(
        group["ParameterApplyStatus"] == "pending-reboot"
        for group in instance["DBParameterGroups"]
    )
    if not any([pending_values, pending_parameter_group]):
        logging.info(
            "No pending modifications. Nothing to do.",
        )
    elif configureLoggingRestart:
        logging.info(
            "Instance requires reboot.",
        )
        rds_client.reboot_db_instance(
            DBInstanceIdentifier=server,
        )
        logging.info(
            "Instance rebooted. Waiting to start.",
        )
        waiter = rds_client.get_waiter("db_instance_available")
        waiter.wait(DBInstanceIdentifier=server)
        logging.info("Instance started after reboot.")
    else:
        logging.warn(
            "Pending modifications. They will probably be applied during the next maintenance window.",
        )


def handler(event, context):
    logger.info(json.dumps(event))
    try:
        properties = event["ResourceProperties"]
        # role = properties["RedshiftRole"]
        server = properties["ServerName"]
        # bucket = properties["Bucket"]
        # db = properties["Db"]
        # dbUser = properties["DbUser"]
        configureLogging = properties["ConfigureLogging"] == "true"
        configureLoggingRestart = properties["ConfigureLoggingRestart"] == "true"

        if event["RequestType"] == "Delete":
            cfnresponse.send(
                event, context, cfnresponse.SUCCESS, {"Data": "Delete complete"}
            )
        else:
            ensure_valid_cluster_engine(server)
            ensure_custom_parameter_group(server, configureLogging)
            logging.info("Custom parameter group of instance configured successfully.")
            ensure_parameter_set(server, configureLogging, "log_statement", "all")
            ensure_parameter_set(
                server, configureLogging, "log_min_duration_statement", "0"
            )
            logging.info("Custom parameter group configured successfully.")
            ensure_log_exporting_enabled(server, configureLogging)
            logging.info("Custom log exporting configured successfully")
            ensure_instance_restarted(server, configureLoggingRestart)

            return cfnresponse.send(
                event,
                context,
                cfnresponse.SUCCESS,
                {},
                # {"LogGroup": logging_bucket},
                reason="Create complete",
            )
    except DataException as e:
        logger.error(e)
        return cfnresponse.send(
            event,
            context,
            cfnresponse.FAILED,
            {},
            reason="{}. See the details in CloudWatch Log Stream: {}".format(
                str(e), context.log_stream_name
            ),
        )
    except Exception as e:
        logging.error(e)
        return cfnresponse.send(
            event,
            context,
            cfnresponse.FAILED,
            {},
            reason="Something failed. See the details in CloudWatch Log Stream: {}".format(
                context.log_stream_name
            ),
        )
