"""
A lambda function handler that decrypts and pre-processes encrypted DAS streams
for use in AWS Firehose.

Based on:
https://github.com/aws-samples/decrypt-das-aws-rds/blob/main/rds-das-decrypt-kinesis-firehose.py
"""

from __future__ import print_function
import os
import json
import base64
import zlib
import boto3
import aws_encryption_sdk
from aws_encryption_sdk import CommitmentPolicy
from aws_encryption_sdk.internal.crypto import WrappingKey
from aws_encryption_sdk.key_providers.raw import RawMasterKeyProvider
from aws_encryption_sdk.identifiers import WrappingAlgorithm, EncryptionKeyType

DAS_EVENT_TYPE = "DatabaseActivityMonitoringRecord"

REGION_NAME = os.environ["AWS_REGION"]
KMS_KEY_ARN = os.environ["kms_key_arn"]
RDS_RESOURCE_ID = os.environ["rds_resource_id"]

enc_client = aws_encryption_sdk.EncryptionSDKClient(
    commitment_policy=CommitmentPolicy.REQUIRE_ENCRYPT_ALLOW_DECRYPT
)
kms_region = KMS_KEY_ARN.split(":")[3]
kms = boto3.client("kms", region_name=kms_region)

disallowed_events = {
    "oracle": {
        "command": {},
    },
    "sqlserver": {"class": {"LOGIN"}},
}


def is_allowed_event(event):
    if "type" not in event or event["type"] != "record":
        return False

    if "command" not in event or "serverType" not in event:
        return False

    disallowed = disallowed_events[event["serverType"].lower()]
    for field, excluded in disallowed.items():
        if field in event and event[field] in excluded:
            return False

    return True


class MyRawMasterKeyProvider(RawMasterKeyProvider):
    """
    A key provider for decrypting DAS data.
    """

    provider_id = "BC"

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls)
        return obj

    def __init__(self, plain_key):
        RawMasterKeyProvider.__init__(self)
        self.wrapping_key = WrappingKey(
            wrapping_algorithm=WrappingAlgorithm.AES_256_GCM_IV12_TAG16_NO_PADDING,
            wrapping_key=plain_key,
            wrapping_key_type=EncryptionKeyType.SYMMETRIC,
        )

    def _get_raw_key(self, _key_id):
        return self.wrapping_key


def decrypt_payload(payload, data_key):
    """
    Decrypt the data portion of a DAS record set.
    """
    my_key_provider = MyRawMasterKeyProvider(data_key)
    my_key_provider.add_master_key("DataKey")
    materials_manager = (
        aws_encryption_sdk.materials_managers.default.DefaultCryptoMaterialsManager(
            master_key_provider=my_key_provider
        )
    )
    # Decrypt the records using the master key.
    decrypted_plaintext, _header = enc_client.decrypt(
        source=payload, materials_manager=materials_manager
    )
    return decrypted_plaintext


def decrypt_decompress(payload, key):
    """
    Decrypt and decompress a DAS record set.
    """
    decrypted = decrypt_payload(payload, key)
    try:
        return zlib.decompress(decrypted, zlib.MAX_WBITS + 16)
    except Exception as e:
        print("An exception occurred:", e)


def filter_database_activity_events(das_event):
    """
    Filter out non-conforming DAS records, and remove heartbeat events from
    valid DAS records to reduce output stream size.
    """
    if "type" not in das_event:
        print(
            "Unexpected record format in database activity stream."
            "Dropping record. Fields:",
            das_event.keys(),
        )
        return None

    if das_event["type"] != DAS_EVENT_TYPE:
        print("Unexpected record type in database activity stream:", das_event["type"])
        return None

    if "databaseActivityEventList" not in das_event:
        print(
            "Dropping record set with non-matching structure. Fields:", das_event.keys()
        )
        return None
    received = len(das_event["databaseActivityEventList"])
    das_event["databaseActivityEventList"] = [
        e for e in das_event["databaseActivityEventList"] if is_allowed_event(e)
    ]
    filtered = len(das_event["databaseActivityEventList"])

    if len(das_event["databaseActivityEventList"]) < 1:
        return None

    return das_event, received, filtered


def lambda_handler(event, _context):
    """
    Process a batch of DAS events.
    """
    output = []
    for record in event["records"]:
        data = base64.b64decode(record["data"])
        record_data = json.loads(data)

        # Decode and decrypt the payload
        payload_decoded = base64.b64decode(record_data["databaseActivityEvents"])
        data_key_decoded = base64.b64decode(record_data["key"])

        if "db" in RDS_RESOURCE_ID:
            encryption_context = {"aws:rds:db-id": RDS_RESOURCE_ID}
        else:
            encryption_context = {"aws:rds:dbc-id": RDS_RESOURCE_ID}

        data_key_decrypt_result = kms.decrypt(
            CiphertextBlob=data_key_decoded, EncryptionContext=encryption_context
        )

        if (
            decrypt_decompress(payload_decoded, data_key_decrypt_result["Plaintext"])
            is None
        ):
            continue

        plaintext = decrypt_decompress(
            payload_decoded, data_key_decrypt_result["Plaintext"]
        ).decode("utf8")

        event = json.loads(plaintext)
        pruned_event = filter_database_activity_events(event)

        if pruned_event is None:
            output_record = {"recordId": record["recordId"], "result": "Dropped"}
        else:
            das_event, received, filtered = pruned_event
            print(f"Received {received} events, filtered to {filtered} events.")
            plain_event = zlib.compress(
                json.dumps(das_event).encode("utf-8"), wbits=zlib.MAX_WBITS + 16
            )
            packed_event = {
                "databaseActivityEvents": base64.b64encode(plain_event).decode("utf-8")
            }
            output_record = {
                "recordId": record["recordId"],
                "result": "Ok",
                "data": base64.b64encode(
                    json.dumps(packed_event).encode("utf-8")
                ).decode("utf-8"),
            }
        output.append(output_record)
    return {"records": output}
