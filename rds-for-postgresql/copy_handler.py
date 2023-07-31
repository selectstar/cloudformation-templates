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
        srcBucket = properties["srcBucket"]
        srcKey = properties["srcKey"]
        dstBucket = properties["dstBucket"]
        dstKey = properties["dstKey"]
        if event["RequestType"] == "Delete":
            s3_client.delete_object(
                Bucket=dstBucket,
                Key=dstKey,
            )
            cfnresponse.send(
                event, context, cfnresponse.SUCCESS, {"Data": "Delete complete"}
            )
        else:
            s3_client.copy_object(
                Bucket=dstBucket,
                CopySource=f"{srcBucket}/{srcKey}",
                Key=dstKey,
            )
            return cfnresponse.send(
                event,
                context,
                cfnresponse.SUCCESS,
                {
                    "result": "Copy complete",
                    "Copy": {"S3Bucket": dstBucket, "S3Key": dstKey},
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
