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
        logging.info("Finished: %s", statement)
        if response["Status"] != "FINISHED":
            raise DataException("Failed SQL: " + str(response["Error"]))
        return response
    except Exception as e:
        logging.info("Failed Exec Query: %s", e)
        raise e


@retry_aws(codes=["InvalidClusterState"])
def ensure_iam_role(cluster, role):
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
    logging.info("Logging status: %s", logging_status)
    if logging_status["LoggingEnabled"]:  # eg. user already configured s3 logging
        if "BucketName" in logging_status:  # eg. use custom s3 bucket active
            logging_bucket = logging_status["BucketName"]
        else:  # eg. user have CloudWatch as destination activated
            raise DataException(
                "Configure S3 logging failed. Another destination of logging active."
            )
    elif configureS3Logging:
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


@retry_aws(codes=["InvalidClusterParameterGroupState"])
def ensure_custom_parameter_group(cluster, configureS3Logging):
    cluster_description = redshift_client.describe_clusters(ClusterIdentifier=cluster)[
        "Clusters"
    ][0]
    parameter_group_name = cluster_description["ClusterParameterGroups"][0][
        "ParameterGroupName"
    ]
    logging.info("Current parameter group name: %s", parameter_group_name)
    if parameter_group_name.startswith("default."):
        parameter_group = redshift_client.describe_cluster_parameter_groups(
            ParameterGroupName=parameter_group_name
        )["ParameterGroups"][0]
        custom_parameter_group = f"redshift-custom-{cluster}"
        if not configureS3Logging:
            raise DataException(
                "Configure logging failed."
                "Setup logging to S3 must be accepted in CloudFormation or custom parameter group set manually."
            )
        redshift_client.create_cluster_parameter_group(
            ParameterGroupName=custom_parameter_group,
            ParameterGroupFamily=parameter_group["ParameterGroupFamily"],
            Description="Created by CloudFormation on provisioning Select Star",
        )
        logging.info("Custom parameter group created: %s", custom_parameter_group)
        redshift_client.modify_cluster(
            ClusterIdentifier=cluster,
            ClusterParameterGroupName=custom_parameter_group,
        )
        logging.info("Custom parameter set for cluster: %s", custom_parameter_group)
        waiter = redshift_client.get_waiter("cluster_available")
        waiter.wait(ClusterIdentifier=cluster)


@retry_aws(codes=["InvalidClusterParameterGroupState"])
def ensure_user_activity_enabled(cluster, configureS3Logging):
    cluster_description = redshift_client.describe_clusters(ClusterIdentifier=cluster)[
        "Clusters"
    ][0]
    parameter_group = cluster_description["ClusterParameterGroups"][0][
        "ParameterGroupName"
    ]
    logging.info("Parameter group: %s", parameter_group)
    paginator = redshift_client.get_paginator("describe_cluster_parameters")
    enabled = any(
        parameter["ParameterName"] == USER_ACTIVITY
        and parameter["ParameterValue"] == "true"
        for resp in paginator.paginate(ParameterGroupName=parameter_group)
        for parameter in resp["Parameters"]
    )
    if not enabled:
        if not configureS3Logging:
            raise DataException(
                "Configure logging failed."
                f"Setup logging to S3 must be accepted in CloudFormation or parameter '{USER_ACTIVITY}' enabled manually."
            )
        redshift_client.modify_cluster_parameter_group(
            ParameterGroupName=parameter_group,
            Parameters=[
                {
                    "ParameterName": USER_ACTIVITY,
                    "ParameterValue": "true",
                }
            ],
        )
        logging.info("Parameter group updated to set parameter: %s", USER_ACTIVITY)
    waiter = redshift_client.get_waiter("cluster_available")
    waiter.wait(ClusterIdentifier=cluster)


def ensure_cluster_restarted(cluster):
    cluster_description = redshift_client.describe_clusters(ClusterIdentifier=cluster)[
        "Clusters"
    ][0]
    pending_reboot = any(
        param["ParameterName"] == USER_ACTIVITY
        and param["ParameterApplyStatus"] == "pending-reboot"
        for group in cluster_description["ClusterParameterGroups"]
        for param in group["ClusterParameterStatusList"]
    )
    if pending_reboot:
        redshift_client.reboot_cluster(ClusterIdentifier=cluster)
        waiter = redshift_client.get_waiter("cluster_available")
        waiter.wait(ClusterIdentifier=cluster)


def handler(event, context):
    logger.info(json.dumps(event))
    try:
        properties = event["ResourceProperties"]
        role = properties["RedshiftRole"]
        cluster = properties["Cluster"]
        bucket = properties["Bucket"]
        db = properties["Db"]
        dbUser = properties["DbUser"]
        configureS3Logging = properties["ConfigureS3Logging"] == "true"
        configureS3LoggingRestart = properties["ConfigureS3LoggingRestart"] == "true"

        if event["RequestType"] == "Delete":
            try:
                for dbname in db:
                    for table in TABLES:
                        execQuery(
                            cluster,
                            dbname,
                            dbUser,
                            f"revoke all on {table} from selectstar;",
                        )
                execQuery(cluster, db[0], dbUser, "drop user selectstar;")
            except Exception as e:
                logging.info("User could not be removed")

            try:
                redshift_client.modify_cluster_iam_roles(
                    ClusterIdentifier=cluster, RemoveIamRoles=[role]
                )
                logging.info("Cluster IAM role removed: %s", role)
                waiter = redshift_client.get_waiter("cluster_available")
                waiter.wait(ClusterIdentifier=cluster)
            except Exception as e:
                logging.info("Role could not be removed")

            cfnresponse.send(
                event, context, cfnresponse.SUCCESS, {"Data": "Delete complete"}
            )
        else:
            try:
                ensure_iam_role(cluster, role)
            except Exception as e:
                logger.error(e)
                raise DataException("Configure IAM role failed")
            logging.info("IAM role configured successfully")
            # Configure S3 logging for Redshift
            try:
                logging_bucket = ensure_logging_enabled(
                    cluster, configureS3Logging, bucket
                )
            except DataException:
                raise
            except Exception as e:
                logger.error(e)
                raise DataException("Configure logging failed")
            logging.info("S3 logging configured successfully")

            try:
                ensure_custom_parameter_group(cluster, configureS3Logging)
            except DataException:
                raise
            except Exception as e:
                logger.error(e)
                raise DataException("Ensure custom parameter group failed")

            try:
                ensure_user_activity_enabled(cluster, configureS3Logging)
            except DataException:
                raise
            except Exception as e:
                logger.error(e)
                raise DataException("Ensure user activity enabled failed")

            if configureS3LoggingRestart:
                ensure_cluster_restarted(cluster)
            logging.info("User audit logging configured successfully")

            try:
                try:
                    user_stmt = "create user selectstar with password disable syslog access unrestricted;"
                    execQuery(
                        cluster,
                        db[0],
                        dbUser,
                        user_stmt,
                    )
                except Exception as e:
                    logger.warn(
                        f"Ignore failure on user creation. Most likely user already exist"
                    )
                    pass
                    # ignore failure that user exist
                for dbname in db:
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
                logger.error(e)
                return cfnresponse.send(
                    event,
                    context,
                    cfnresponse.FAILED,
                    {},
                    reason="Execute query failed. See the details in CloudWatch Log Stream: {}".format(
                        str(e), context.log_stream_name
                    ),
                )
            return cfnresponse.send(
                event,
                context,
                cfnresponse.SUCCESS,
                {"LoggingBucket": logging_bucket},
                reason="Create complete",
            )
    except DataException as e:
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
