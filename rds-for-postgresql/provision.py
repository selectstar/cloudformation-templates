import json
import logging
import time
from typing import Sequence, Tuple
import cfnresponse
import botocore
import boto3
import psycopg2
from itertools import groupby
from psycopg2 import sql
import httpx
from collections import namedtuple
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
import sentry_sdk
import os
import hashlib
from contextlib import contextmanager

logging.basicConfig(
    format="%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M:%S",
    level=logging.INFO,
)

if "LAMBDA_TASK_ROOT" in os.environ:
    xray_recorder.configure(service="Select Star & AWS RDS for PostgreSQL integration")
    patch_all()

USER_ACTIVITY = "enable_user_activity_logging"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

rds_client = boto3.client("rds")
s3_client = boto3.client("s3")
secret_client = boto3.client("secretsmanager")
ec2_client = boto3.client("ec2")
httpx_transport = httpx.HTTPTransport(retries=3)
httpx_client = httpx.Client(transport=httpx_transport)

if "SENTRY_DSN" in os.environ:
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        traces_sample_rate=0.0,
    )
    logger.info("Sentry DSN reporting initialized")


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


def fetch_instance(server):
    try:
        instances = rds_client.describe_db_instances(DBInstanceIdentifier=server)[
            "DBInstances"
        ]
        return instances[0]
    except botocore.exceptions.ClientError as err:
        if err.response["Error"]["Code"] == "DBInstanceNotFound":
            raise DataException(
                f"Provisiong failed. DB instannce '{server}' not found. Verify DB instance name."
            ) from err
        raise err


def determine_primary_server(server):
    instance = fetch_instance(server)
    return instance.get("ReadReplicaSourceDBInstanceIdentifier", server)


def ensure_valid_cluster_engine(server):
    instance = fetch_instance(server)
    if instance["Engine"] not in ["postgres", "aurora-postgresql"]:
        raise DataException(
            "Unsupported DB engine - required 'postgres', or 'aurora-postgresql'. Verify engine of DB instance."
        )
    if not instance["PubliclyAccessible"]:
        raise DataException(
            "Instance must be publicly available. Update the instance configurations and try again."
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


def ensure_custom_parameter_group(server, configureLogging):
    instance = rds_client.describe_db_instances(DBInstanceIdentifier=server)[
        "DBInstances"
    ][0]
    enabled_custom_parameter = any(
        not group["DBParameterGroupName"].startswith("default.")
        for group in instance["DBParameterGroups"]
    )
    logger.info(
        "Determined DB instance parameter group. Enabled custom parameter group: %s",
        enabled_custom_parameter,
    )

    if enabled_custom_parameter:
        logger.info(
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
            raise DataException(
                "Configure logging failed."
                "Unable to determine db parameter group family for cluster."
            )
        parameter_group = f"custom-{server}"
        rds_client.create_db_parameter_group(
            Description="Created by Select Star via CloudFormation. Enables logging queries to CloudWatch.",
            DBParameterGroupName=parameter_group,
            DBParameterGroupFamily=family,
        )
        logger.info("A new parameter group created: %s", parameter_group)
        rds_client.modify_db_instance(
            DBInstanceIdentifier=server,
            ApplyImmediately=False,
            DBParameterGroupName=parameter_group,
        )
        logger.info(
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


def find_parameter(name, parameters):
    for param in parameters:
        if param["ParameterName"] == name:
            return param


def ensure_parameter_set(server, configureLogging, name, value):
    instance = rds_client.describe_db_instances(DBInstanceIdentifier=server)[
        "DBInstances"
    ][0]
    parameter_groups = (
        group["DBParameterGroupName"]
        for group in instance["DBParameterGroups"]
        if not group["DBParameterGroupName"].startswith("default.")
    )

    paginator = rds_client.get_paginator("describe_db_parameters")
    found_parameter = None
    target_parameter_group = None

    for parameter_group in parameter_groups:
        if target_parameter_group is None:
            # use the first parameter group as the target to set the parameter in, in case it's not found.
            target_parameter_group = parameter_group

        for page in paginator.paginate(DBParameterGroupName=parameter_group):
            found_parameter = find_parameter(name, page["Parameters"])
            if found_parameter is not None:
                target_parameter_group = parameter_group
                break
        if found_parameter is not None:
            break

    if found_parameter is not None and found_parameter.get("ParameterValue") == value:
        logger.info(
            "Parameter '%s' of parameter group '%s' already set to '%s'. Nothing to do.",
            name,
            target_parameter_group,
            value,
        )
    elif configureLogging:
        rds_client.modify_db_parameter_group(
            DBParameterGroupName=target_parameter_group,
            Parameters=[
                {
                    "ParameterName": name,
                    "ParameterValue": value,
                    "ApplyMethod": "pending-reboot",
                },
            ],
        )
        logger.info(
            "Parameter '%s' of parameter group '%s' update to '%s'. ",
            name,
            target_parameter_group,
            value,
        )
    else:
        raise DataException(
            "Configure logging failed."
            f"Setup logging must be accepted in CloudFormation or manually update parameter '{name}' of parameter group '{target_parameter_group}' to '{value}'."
        )


def ensure_log_exporting_enabled(server, configureLogging, dbEngine):
    instance = rds_client.describe_db_instances(DBInstanceIdentifier=server)[
        "DBInstances"
    ][0]
    enabled_log_export = instance.get("EnabledCloudwatchLogsExports", [])
    if dbEngine in enabled_log_export:
        logger.info("Log export configured. Nothing to do.")
    elif configureLogging:
        rds_client.modify_db_instance(
            DBInstanceIdentifier=server,
            ApplyImmediately=False,
            CloudwatchLogsExportConfiguration={
                "EnableLogTypes": [
                    dbEngine,
                ],
            },
        )
        logger.info(
            "Exporting to CloudWatch enabling. Waiting to apply.",
        )
        waiter = rds_client.get_waiter("db_instance_available")
        waiter.wait(DBInstanceIdentifier=server)
        logger.info(
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
        logger.info(
            "No pending modifications. Nothing to do.",
        )
    elif configureLoggingRestart:
        logger.info(
            "Instance requires reboot.",
        )
        rds_client.reboot_db_instance(
            DBInstanceIdentifier=server,
        )
        logger.info(
            "Instance rebooted. Waiting to start.",
        )
        waiter = rds_client.get_waiter("db_instance_available")
        waiter.wait(DBInstanceIdentifier=server)
        logger.info("Instance started after reboot.")
    else:
        logger.warning(
            "Pending modifications. They will probably be applied during the next maintenance window.",
        )


def str2hash(value):
    return hashlib.md5(value.encode()).digest()


def execQuery(cur, text, noEcho=False, **parameters):
    q = sql.SQL(text).format(**parameters)

    query_string = cur.mogrify(q).decode("utf-8")
    if noEcho:
        query_string = "*" * len(query_string)

    logger.info(
        "Executing SQL on database '%s': %s", cur.connection.info.dbname, query_string
    )
    return cur.execute(q)


SchemaItem = namedtuple("SchemaItem", ["db_name", "schema"])


def get_ip_address() -> str:
    try:
        ip_response = httpx_client.get("https://httpbin.org/ip", timeout=60.0)
        ip_response.raise_for_status()
        ip = ip_response.json()["origin"]
    except httpx.HTTPError as exc:
        logger.exception(
            f"An error occurred while requesting {exc.request.url!r}. Trying another service.."
        )

        # Try another service in case of httpbin unavailability
        try:
            ip_response = httpx_client.get("https://ifconfig.me/ip", timeout=60.0)
            ip_response.raise_for_status()
            ip = ip_response.text
        except httpx.HTTPError as exc2:
            logger.exception(
                f"An error occurred while requesting {exc2.request.url!r}."
            )
            raise

    return ip


def create_ingress_rules(instance) -> Tuple[str, Sequence[str]]:
    ip = get_ip_address()
    logger.info(f"IP Address: {ip}")

    security_group_id = next(
        (x["VpcSecurityGroupId"] for x in instance["VpcSecurityGroups"]), None
    )
    if not security_group_id:
        return None, []
    port = instance["Endpoint"]["Port"]
    try:
        security_groups_rules = ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    "IpRanges": [
                        {
                            "CidrIp": f"{ip}/32",
                            "Description": "Temporary access to provision Select Star integration",
                        },
                    ],
                    "IpProtocol": "tcp",
                    "FromPort": port,
                    "ToPort": port,
                }
            ],
        )["SecurityGroupRules"]
        rules_ids = [rule["SecurityGroupRuleId"] for rule in security_groups_rules]
        logger.info(
            "Added temporary ingress rule to enable access from '%s' to '%s' (port: %s): %s",
            ip,
            security_group_id,
            port,
            rules_ids,
        )
        return security_group_id, rules_ids
    except botocore.exceptions.ClientError as err:
        # no need to add a new rule, it is there
        if err.response["Error"]["Code"] == "InvalidPermission.Duplicate":
            logger.warning("Temporary ingress rule to enable access exist. Skipping")
            return security_group_id, []
        else:
            raise err


def remove_ingress_rules(security_group_id, security_groups_rules):
    if not security_groups_rules:
        return
    ec2_client.revoke_security_group_ingress(
        GroupId=security_group_id,
        SecurityGroupRuleIds=security_groups_rules,
    )
    logger.info("Removed temporary ingress rules: %s", security_groups_rules)


@contextmanager
def connect_instance(instance, user, dbname, password):
    """
    Create connection & cursor for AWS RDS for PostgreSQL

    It also temporarily opens security group ingress to allow this connection
    """
    logger.info("Connecting to RDS instance: %s", instance["DBInstanceIdentifier"])
    security_group_id, security_groups_rules = create_ingress_rules(instance)
    with psycopg2.connect(
        host=instance["Endpoint"]["Address"],
        port=instance["Endpoint"]["Port"],
        user=user,
        dbname=dbname,
        password=password,
        connect_timeout=10,
    ) as conn, conn.cursor() as cur:
        logger.info("Successfully connected to PostgreSQL database '%s'", dbname)
        yield cur
        remove_ingress_rules(security_group_id, security_groups_rules)


def ensure_user_created(server, schema, user, password, secretArn):
    instance = rds_client.describe_db_instances(DBInstanceIdentifier=server)[
        "DBInstances"
    ][0]
    secret_response = secret_client.get_secret_value(SecretId=secretArn)
    secret = json.loads(secret_response["SecretString"])
    logger.info("Successfully retrieved & decoded secret: %s", secretArn)
    with connect_instance(
        instance=instance,
        user=user,
        # 'postgres' is almost guaranteed that it will exist. Ref: https://stackoverflow.com/a/27731233
        dbname="postgres",
        password=password,
    ) as cur:
        execQuery(
            cur,
            "CREATE USER {user} WITH encrypted password {password}",
            noEcho=True,
            user=sql.Identifier(secret["username"]),
            password=sql.Literal(secret["password"]),
        )
        for x in schema:
            if x.db_name != "*":
                continue
            cur.execute(
                sql.SQL(
                    "select datname from pg_catalog.pg_database where datallowconn = true and has_database_privilege({user}, datname, 'connect')"
                ).format(user=sql.Literal(user))
            )
            new_items = [SchemaItem(row[0], x.schema) for row in cur.fetchall()]
            logger.info("Resolve placeholder in '*' to new schemas: %s", new_items)
            schema.extend(new_items)
    for db_name, db_schemas in groupby(schema, key=lambda x: x.db_name):
        if db_name == "*":
            continue
        with connect_instance(
            instance=instance,
            user=user,
            dbname=db_name,
            password=password,
        ) as cur:
            execQuery(
                cur,
                "GRANT CONNECT ON DATABASE {name} TO {user};",
                name=sql.Identifier(db_name),
                user=sql.Identifier(secret["username"]),
            )
            for x in db_schemas:
                if not x.schema == "*":
                    continue
                cur.execute(
                    "SELECT nspname FROM pg_catalog.pg_namespace where nspname not like 'pg_%';"
                )
                db_schemas = [SchemaItem(x.db_name, row[0]) for row in cur.fetchall()]
                logger.info("Resolve placeholder '*' to schemas: %s", db_schemas)
            for schema_item in db_schemas:
                execQuery(
                    cur,
                    "GRANT USAGE ON SCHEMA {name} TO {user};",
                    name=sql.Identifier(schema_item.schema),
                    user=sql.Identifier(secret["username"]),
                )
                execQuery(
                    cur,
                    "GRANT SELECT ON ALL TABLES IN SCHEMA {name} TO {user};",
                    name=sql.Identifier(schema_item.schema),
                    user=sql.Identifier(secret["username"]),
                )
                execQuery(
                    cur,
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {name} GRANT SELECT ON TABLES TO {user};",
                    name=sql.Identifier(schema_item.schema),
                    user=sql.Identifier(secret["username"]),
                )


def ensure_user_database_revoked(cur, username, dbs):
    for name in dbs:
        execQuery(
            cur,
            "REVOKE ALL PRIVILEGES ON DATABASE {name} FROM {user};",
            name=sql.Identifier(name),
            user=sql.Identifier(username),
        )


def ensure_user_schema_revoked(cur, username):
    cur.execute(
        # PostgreSQL recommends avoid schema pg_ as reserved for system catalog schema
        # References: https://www.postgresql.org/docs/current/ddl-schemas.html#DDL-SCHEMAS-CATALOG
        sql.SQL(
            "SELECT nspname FROM pg_catalog.pg_namespace where nspname not like 'pg_%';"
        ).format(user=sql.Literal(username))
    )
    schema = [row[0] for row in cur.fetchall()]
    logger.info("Determined schemas to revoke permission: %s", schema)
    for name in schema:
        execQuery(
            cur,
            "REVOKE ALL ON SCHEMA {name} FROM {user};",
            name=sql.Identifier(name),
            user=sql.Identifier(username),
        )
        execQuery(
            cur,
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {name} REVOKE ALL ON TABLES FROM {user};",
            name=sql.Identifier(name),
            user=sql.Identifier(username),
        )
        execQuery(
            cur,
            "REVOKE ALL ON ALL TABLES IN SCHEMA {name} FROM {user};",
            name=sql.Identifier(name),
            user=sql.Identifier(username),
        )


def ensure_user_removed(server, user, password, secretArn):
    instance = rds_client.describe_db_instances(DBInstanceIdentifier=server)[
        "DBInstances"
    ][0]
    secret_response = secret_client.get_secret_value(SecretId=secretArn)
    secret = json.loads(secret_response["SecretString"])
    logger.info("Successfully retrieved & decoded secret: %s", secretArn)
    with connect_instance(
        instance=instance,
        user=user,
        # 'postgres' is almost guaranteed that it will exist. Ref: https://stackoverflow.com/a/27731233
        dbname="postgres",
        password=password,
    ) as cur:
        cur.execute(
            sql.SQL(
                "select datname from pg_catalog.pg_database where datallowconn = true and has_database_privilege({user}, datname, 'connect')"
            ).format(user=sql.Literal(secret["username"]))
        )
        dbs = [row[0] for row in cur.fetchall()]
        ensure_user_database_revoked(cur, secret["username"], dbs)
    for dbname in dbs:
        try:
            with connect_instance(
                instance=instance,
                user=user,
                dbname=dbname,
                password=password,
            ) as cur:
                ensure_user_schema_revoked(cur, secret["username"])
        except Exception as e:
            logger.warning(
                "Failed to revoke permission in database '%s': %s",
                dbname,
                e,
                exc_info=True,
            )
    with connect_instance(
        instance=instance,
        user=user,
        # 'postgres' is almost guaranteed that it will exist. Ref: https://stackoverflow.com/a/27731233
        dbname="postgres",
        password=password,
    ) as cur:
        try:
            execQuery(
                cur,
                "DROP USER IF EXISTS {user};",
                user=sql.Identifier(secret["username"]),
            )
        except psycopg2.errors.UndefinedObject:
            logger.warning("User not deleted because it did not exist.")


def handler(event, context):
    try:
        properties = event["ResourceProperties"]

        dbPassword = properties["DbPassword"]
        properties["DbPassword"] = "*" * len(
            dbPassword
        )  # redact password before logging
        logger.info(json.dumps(event))

        server = properties["ServerName"]

        schema = [SchemaItem(*x.split(".")) for x in properties["Schema"].split(",")]
        dbUser = properties["DbUser"]
        dbEngine = properties["DbEngine"]
        secretArn = properties["secretArn"]
        configureLogging = properties["ConfigureLogging"] == "true"
        configureLoggingRestart = properties["ConfigureLoggingRestart"] == "true"

        if event["RequestType"] == "Delete":
            primary_server = determine_primary_server(server)
            ensure_user_removed(primary_server, dbUser, dbPassword, secretArn)
            logger.info("User removed successfully")

            cfnresponse.send(
                event, context, cfnresponse.SUCCESS, {"Data": "Delete complete"}
            )
        else:
            security_group_id, endpoint_port = ensure_valid_cluster_engine(server)
            primary_server = determine_primary_server(server)
            ensure_custom_parameter_group(server, configureLogging)
            logger.info("Custom parameter group of instance configured successfully.")
            ensure_parameter_set(server, configureLogging, "log_statement", "all")
            ensure_parameter_set(
                server, configureLogging, "log_min_duration_statement", "0"
            )
            logger.info("Custom parameter group configured successfully.")
            ensure_log_exporting_enabled(server, configureLogging, dbEngine)
            logger.info("Custom log exporting configured successfully")
            ensure_instance_restarted(server, configureLoggingRestart)
            logger.info("Successfully ensured instance restarted (if allowed)")
            # read-only replicas needs updates user configuration on primary
            ensure_user_created(primary_server, schema, dbUser, dbPassword, secretArn)

            return cfnresponse.send(
                event,
                context,
                cfnresponse.SUCCESS,
                {
                    "EndpointPort": endpoint_port,
                    "SecurityGroupId": security_group_id,
                },
                # {"LogGroup": logging_bucket},
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
