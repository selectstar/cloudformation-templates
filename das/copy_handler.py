import json
import logging
import cfnresponse
import boto3

logging.basicConfig(
    format="%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M:%S",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")


def handler(event, context):
    logger.info(json.dumps(event))
    try:
        properties = event["ResourceProperties"]
        src_bucket = properties["srcBucket"]
        src_key = properties["srcKey"]
        dst_bucket = properties["dstBucket"]
        dst_key = properties["dstKey"]
        if event["RequestType"] == "Delete":
            s3_client.delete_object(
                Bucket=dst_bucket,
                Key=dst_key,
            )
            cfnresponse.send(
                event, context, cfnresponse.SUCCESS, {"Data": "Delete complete"}
            )
        else:
            s3_client.copy_object(
                Bucket=dst_bucket,
                CopySource=f"{src_bucket}/{src_key}",
                Key=dst_key,
            )
            return cfnresponse.send(
                event,
                context,
                cfnresponse.SUCCESS,
                {
                    "result": "Copy complete",
                    "Copy": {"S3Bucket": dst_bucket, "S3Key": dst_key},
                },
                reason="Create complete",
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
