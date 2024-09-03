# DAS Firehose Log Processor

This package transforms Firehose events so they can be read by the S3 ingest
process.

## Packaging and Deployment

The handler must be deployed as an AWS Lambda function that can be called by
AWS Firehose.

### Packaging

To package the bundle for distribution:

Create the wheel:
```
poetry build --format wheel
```

Setup a Lambda package for the wheel:
```
poetry run pip install --upgrade --only-binary :all: --platform manylinux2014_aarch64 --python-version 3.12 --target package --implementation cp dist/*.whl
```

Bundle the package for upload:
```
(cd package; zip -X --no-dir-entries --quiet --recurse-paths ../handler.zip .)
```

### Deployment

One lambda function in needed for each activity stream producer, as environment
variables are used as part of the decryption process and need to be configured
specifically for the DAS producer.

#### Configuring the Lambda Function

Lambda Runtime Settings:

| Options      | Value                                           |
|--------------|-------------------------------------------------|
| Runtime      | Python 3.12                                     |
| Architecture | arm64                                           |
| Handler      | selectstar_das_processor.handler.lambda_handler |

General Configuration:

| Options | Value    |
|---------|----------|
| Timeout | 1 minute |
| Memory  | 128 MB   |

Environment Variables:

| Name            | Description                                               |
|-----------------|-----------------------------------------------------------|
| rds_resource_id | The ARN of the RDS instance or cluster producing the logs |

Required Permissions:

| Action      | Resource                    |
|-------------|-----------------------------|
| kms:Decrypt | The KMS key used by RDS DAS |

#### Configuring Firehose

Source settings:

Kinesis data stream, using the ARN of the Kineses stream that RDS DAS output is
connected to.

Transform and convert records:

| Settings        | Value                                         |
|-----------------|-----------------------------------------------|
| State           | Enabled                                       |
| Lambda Function | Use the ARN for the function deployed above   |
| Buffer Size     | 1 MiB seems to work                           |
| Buffer Interval | 300s or less for testing, 900s for production |

Destination settings:

| Type                 | S3 Bucket                                                                      |
|----------------------|--------------------------------------------------------------------------------|
| Timezone             | UTC                                                                            |
| New line delimiter   | enabled                                                                        |
| Dynamic partitioning | disabled                                                                       |
| S3 bucket prefix     | `processed/!{timestamp:yyyy}/!{timestamp:MM}/!{timestamp:dd}/!{timestamp:HH}/` |
| Buffer size          | 5 MB                                                                           |
| Buffer interval      | 300 seconds                                                                    |
| Encryption           | Use bucket settings                                                            |
