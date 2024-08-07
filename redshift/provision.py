import json
import logging
import time
import cfnresponse
import botocore
import boto3
import os
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
import sentry_sdk

logging.basicConfig(
    format="%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M:%S",
    level=logging.INFO,
)

if "LAMBDA_TASK_ROOT" in os.environ:
    xray_recorder.configure(service="Select Star & AWS RDS for PostgreSQL integration")
    patch_all()

USER_ACTIVITY = "enable_user_activity_logging"
TABLES = [
    "SVV_TABLE_INFO",
    "SVV_TABLES",
    "SVV_COLUMNS",
    "STL_QUERYTEXT",
    "STL_DDLTEXT",
    "STL_QUERY",
]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

redshiftdata_client = boto3.client("redshift-data")
redshift_client = boto3.client("redshift")

if "SENTRY_DSN" in os.environ:
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        traces_sample_rate=0.0,
    )
    logger.info("Sentry DSN reporting initialized")


class DataException(Exception):
    pass


def retry_aws(retries=8, codes=[]):
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


def execQuery(cluster, db, user, statement):
    try:
        response = redshiftdata_client.execute_statement(
            ClusterIdentifier=cluster, Database=db, DbUser=user, Sql=statement
        )
        response = redshiftdata_client.describe_statement(Id=response["Id"])

        while response["Status"] in ["SUBMITTED", "PICKED", "STARTED"]:
            time.sleep(2)
            response = redshiftdata_client.describe_statement(Id=response["Id"])
        if response["HasResultSet"]:
            response["Records"] = redshiftdata_client.get_statement_result(
                Id=response["Id"]
            )["Records"]
        logger.info("Finished: %s", statement)
        if response["Status"] != "FINISHED":
            raise DataException("Failed SQL: " + str(response["Error"]))
        return response
    except Exception as e:
        logger.info("Failed Exec Query: %s", e)
        raise e


def ensure_cluster_state(cluster):
    try:
        instances = redshift_client.describe_clusters(ClusterIdentifier=cluster)[
            "Clusters"
        ]
    except botocore.exceptions.ClientError as err:
        if err.response["Error"]["Code"] == "ClusterNotFound":
            raise DataException(
                f"Operation failed. Cluster '{cluster}' not found. Verify DB instance name."
            ) from err
        raise err
    instance = instances[0]

    logger.info("Cluster status is '%s'. ", instance["ClusterStatus"])
    if instance["ClusterStatus"] == "paused":
        raise DataException(
            f"Cluster status must be 'available'. Status is '{instance['ClusterStatus']}'. Resume the cluster and try again."
        )
    if instance["ClusterStatus"] != "available":
        raise DataException(
            f"Cluster status must be 'available'. Status is '{instance['ClusterStatus']}'. Update the cluster configurations and try again."
        )
    logger.info("Publicly accessible status is '%s'. ", instance["PubliclyAccessible"])


def ensure_valid_cluster(cluster, ConfigureNetwork):
    try:
        instances = redshift_client.describe_clusters(ClusterIdentifier=cluster)[
            "Clusters"
        ]
    except botocore.exceptions.ClientError as err:
        if err.response["Error"]["Code"] == "ClusterNotFound":
            raise DataException(
                f"Provisiong failed. Cluster '{cluster}' not found. Verify DB instance name."
            ) from err
        raise err
    instance = instances[0]
    if not instance["PubliclyAccessible"] and ConfigureNetwork:
        raise DataException(
            "Cluster must be publicly available. Update the cluster configurations (https://aws.amazon.com/premiumsupport/knowledge-center/redshift-cluster-private-public/) and try again."
        )
    security_group_id = [
        x["VpcSecurityGroupId"]
        for x in instance["VpcSecurityGroups"]
        if x["Status"] == "active"
    ][0]
    logger.info("Determined security group ID: %s", security_group_id)
    endpoint_port = instance["Endpoint"]["Port"]
    logger.info("Determined endpoint port: %s", endpoint_port)
    return security_group_id, endpoint_port


@retry_aws(codes=["InvalidClusterState"])
def ensure_iam_role(cluster, role):
    cluster_description = redshift_client.describe_clusters(ClusterIdentifier=cluster)[
        "Clusters"
    ][0]
    enabled = any(
        iam_role["IamRoleArn"] == role for iam_role in cluster_description["IamRoles"]
    )
    if enabled:
        logger.info(
            "IAM role added to cluster. Nothing to do.",
        )
    else:
        logger.info("Add IAM role to cluster required.")
        redshift_client.modify_cluster_iam_roles(
            ClusterIdentifier=cluster, AddIamRoles=[role]
        )
        waiter = redshift_client.get_waiter("cluster_available")
        waiter.wait(ClusterIdentifier=cluster)


@retry_aws(codes=["InvalidClusterState"])
def ensure_logging_enabled(cluster, configureS3Logging, bucket):
    logging_status = redshift_client.describe_logging_status(
        ClusterIdentifier=cluster,
    )
    logger.info("Logging status: %s", logging_status)
    logging_bucket = None
    # eg. user already configured logging (S3 or CW)
    if logging_status["LoggingEnabled"]:
        if "BucketName" in logging_status:  # use S3 logging
            logging_bucket = logging_status["BucketName"]
    elif configureS3Logging:
        logger.info("Enable logging required.")
        redshift_client.enable_logging(
            ClusterIdentifier=cluster,
            BucketName=bucket,
            S3KeyPrefix=f"redshift-logs/{cluster}",
        )
        waiter = redshift_client.get_waiter("cluster_available")
        waiter.wait(ClusterIdentifier=cluster)
        logging_bucket = bucket
    else:
        raise DataException(
            "Configure logging failed."
            "Setup logging to S3 must be accepted in CloudFormation or enable logging manually."
        )
    return logging_bucket


def create_cluster_parameter_group(parameter_group, prefix):
    suffix = ""
    for i in range(10):
        try:
            name = f"{prefix}{suffix}"
            suffix = f"-{i}"
            logger.info("Creating new parameter group with name: %s", name)
            redshift_client.create_cluster_parameter_group(
                ParameterGroupName=name,
                ParameterGroupFamily=parameter_group["ParameterGroupFamily"],
                Description="Created by CloudFormation on provisioning Select Star",
            )
            return name
        except (
            redshift_client.exceptions.ClusterParameterGroupAlreadyExistsFault
        ) as err:
            logger.warn(f"API call failed ({err}); continue with new suffix...")
            continue
    raise DataException(
        "Unable to create new cluster paramter group. Failed to find a new unique name. "
        + "Create and add custom parameter group to the Redshift cluster manually and try again."
    )


@retry_aws(codes=["InvalidClusterParameterGroupState"])
def ensure_custom_parameter_group(cluster, configureS3Logging):
    cluster_description = redshift_client.describe_clusters(ClusterIdentifier=cluster)[
        "Clusters"
    ][0]
    parameter_group_name = cluster_description["ClusterParameterGroups"][0][
        "ParameterGroupName"
    ]
    logger.info("Current parameter group name: %s", parameter_group_name)
    if not parameter_group_name.startswith("default."):
        logger.info(
            "Custom parameter group used. Nothing to do.",
        )
    elif configureS3Logging:
        logger.info("Create a new parameter group required.")
        parameter_group = redshift_client.describe_cluster_parameter_groups(
            ParameterGroupName=parameter_group_name
        )["ParameterGroups"][0]
        custom_parameter_group = create_cluster_parameter_group(
            parameter_group=parameter_group, prefix=f"redshift-custom-{cluster}"
        )
        logger.info("Custom parameter group created: %s", custom_parameter_group)
        redshift_client.modify_cluster(
            ClusterIdentifier=cluster,
            ClusterParameterGroupName=custom_parameter_group,
        )
        logger.info("Custom parameter set for cluster: %s", custom_parameter_group)
        waiter = redshift_client.get_waiter("cluster_available")
        waiter.wait(ClusterIdentifier=cluster)
    else:
        raise DataException(
            "Configure logging failed."
            "Setup logging to S3 must be accepted in CloudFormation or custom parameter group set manually."
        )


@retry_aws(codes=["InvalidClusterParameterGroupState"])
def ensure_user_activity_enabled(cluster, configureS3Logging):
    cluster_description = redshift_client.describe_clusters(ClusterIdentifier=cluster)[
        "Clusters"
    ][0]
    parameter_group = cluster_description["ClusterParameterGroups"][0][
        "ParameterGroupName"
    ]
    logger.info("Parameter group: %s", parameter_group)
    paginator = redshift_client.get_paginator("describe_cluster_parameters")
    enabled = any(
        parameter["ParameterName"] == USER_ACTIVITY
        and parameter["ParameterValue"] == "true"
        for resp in paginator.paginate(ParameterGroupName=parameter_group)
        for parameter in resp["Parameters"]
    )
    if enabled:
        logger.info(
            "User activity enabled. Nothing to do.",
        )
    elif configureS3Logging:
        redshift_client.modify_cluster_parameter_group(
            ParameterGroupName=parameter_group,
            Parameters=[
                {
                    "ParameterName": USER_ACTIVITY,
                    "ParameterValue": "true",
                }
            ],
        )
        logger.info("Parameter group updated to set parameter: %s", USER_ACTIVITY)
        waiter = redshift_client.get_waiter("cluster_available")
        waiter.wait(ClusterIdentifier=cluster)
    else:
        raise DataException(
            "Configure logging failed."
            f"Setup logging to S3 must be accepted in CloudFormation or parameter '{USER_ACTIVITY}' enabled manually."
        )


@retry_aws(codes=["InvalidClusterState"])
def ensure_cluster_restarted(cluster, configureS3LoggingRestart):
    cluster_description = redshift_client.describe_clusters(ClusterIdentifier=cluster)[
        "Clusters"
    ][0]
    pending_reboot = any(
        group["ParameterApplyStatus"] != "in-sync"
        for group in cluster_description["ClusterParameterGroups"]
    )
    if not pending_reboot:
        logger.info(
            "No pending modifications. Nothing to do.",
        )
    elif configureS3LoggingRestart:
        logger.info(
            "Cluster requires reboot.",
        )
        redshift_client.reboot_cluster(ClusterIdentifier=cluster)
        logger.info(
            "Cluster rebooted. Waiting to start.",
        )
        waiter = redshift_client.get_waiter("cluster_available")
        waiter.wait(ClusterIdentifier=cluster)
        logger.info("Cluster started after reboot.")
    else:
        logger.warn(
            "Pending modifications. They will probably be applied during the next maintenance window.",
        )


SKIP_DB = [
    "awsdatacatalog",
    "sys:internal",
    # database for AWS Glue Data Catalog is a preview feature - https://app.shortcut.com/select-star/story/57903
    # contact sales if you need to activate AWS Glue Data Catalog support
]


def fetch_databases(cluster, db, dbUser):
    for resp in redshiftdata_client.get_paginator("list_databases").paginate(
        ClusterIdentifier=cluster,
        Database=db,
        DbUser=dbUser,
    ):
        for database in resp["Databases"]:
            if database not in SKIP_DB:
                yield database


def handler(event, context):
    logger.info(json.dumps(event))
    try:
        properties = event["ResourceProperties"]
        role = properties["RedshiftRole"]
        cluster = properties["Cluster"]
        bucket = properties.get("Bucket", None)
        db = properties["Db"]
        grant = properties["Grant"]
        dbUser = properties["DbUser"]
        configureS3Logging = properties["ConfigureS3Logging"] == "true"
        configureS3LoggingRestart = properties["ConfigureS3LoggingRestart"] == "true"
        ConfigureNetwork = properties["ConfigureNetwork"] == "true"

        ensure_cluster_state(cluster)

        if "*" in grant:
            grant = list(fetch_databases(cluster, db, dbUser))
            logger.info("Resolved '*' in grant to: %s", grant)

        if event["RequestType"] == "Delete":
            try:
                for dbname in grant:
                    for table in TABLES:
                        execQuery(
                            cluster,
                            dbname,
                            dbUser,
                            f"revoke all on {table} from selectstar;",
                        )
                execQuery(cluster, db, dbUser, "drop user selectstar;")
            except Exception:
                logger.warn("User could not be removed")

            try:
                redshift_client.modify_cluster_iam_roles(
                    ClusterIdentifier=cluster, RemoveIamRoles=[role]
                )
                logger.info("Cluster IAM role removed: %s", role)
                waiter = redshift_client.get_waiter("cluster_available")
                waiter.wait(ClusterIdentifier=cluster)
            except Exception:
                logger.warn("Role could not be removed")

            cfnresponse.send(
                event, context, cfnresponse.SUCCESS, {"Data": "Delete complete"}
            )
        else:
            security_group_id, endpoint_port = ensure_valid_cluster(
                cluster, ConfigureNetwork
            )
            logger.info("Ćluster validated successfully")

            ensure_iam_role(cluster, role)
            logger.info("IAM role configured successfully")

            logging_bucket = ensure_logging_enabled(cluster, configureS3Logging, bucket)
            logger.info("S3 logging configured successfully")

            ensure_custom_parameter_group(cluster, configureS3Logging)
            logger.info("Ensured a custom parameter group")

            ensure_user_activity_enabled(cluster, configureS3Logging)
            logger.info("Ensured a user activity enabled")

            ensure_cluster_restarted(cluster, configureS3LoggingRestart)
            logger.info("User audit logging configured successfully")

            try:
                try:
                    user_stmt = "create user selectstar with password disable syslog access unrestricted;"
                    execQuery(
                        cluster,
                        db,
                        dbUser,
                        user_stmt,
                    )
                except Exception:
                    logger.warn(
                        f"Ignore failure on user creation. Most likely user already exist"
                    )
                    pass
                    # ignore failure that user exist
                for dbname in grant:
                    for table in TABLES:
                        execQuery(
                            cluster,
                            dbname,
                            dbUser,
                            f"grant select on {table} to selectstar;",
                        )
            except DataException:
                raise
            except Exception as e:
                raise DataException(f"Execute query failed ({e})")
            return cfnresponse.send(
                event,
                context,
                cfnresponse.SUCCESS,
                {
                    "LoggingBucket": logging_bucket or bucket or "dummy-bucket",
                    "EndpointPort": endpoint_port,
                    "SecurityGroupId": security_group_id,
                },
                reason="Create complete",
            )
    except DataException as e:
        logger.exception("Operation failed and custom error message reported")
        return cfnresponse.send(
            event,
            context,
            cfnresponse.FAILED,
            {},
            reason="{}. See the details in CloudWatch Log Stream: {}".format(
                str(e), context.log_stream_name
            ),
        )
    except Exception:
        logger.exception("Unexpected failure")
        return cfnresponse.send(
            event,
            context,
            cfnresponse.FAILED,
            {},
            reason="Something failed. See the details in CloudWatch Log Stream: {}".format(
                context.log_stream_name
            ),
        )
