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


def handler(event, context):
    logger.info(json.dumps(event))
    try:
        properties = event["ResourceProperties"]
        items = properties["Items"]
        prefix = properties["Prefix"]
        if event["RequestType"] == "Delete":
            cfnresponse.send(
                event, context, cfnresponse.SUCCESS, {"Data": "Delete complete"}
            )
        else:
            return cfnresponse.send(
                event,
                context,
                cfnresponse.SUCCESS,
                {"result": [f"{prefix}{x}" for x in items]},
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
