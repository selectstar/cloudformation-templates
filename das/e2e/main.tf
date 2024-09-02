variable "region" {
  default     = "us-east-2"
  description = "AWS region"
}

variable "name" {
  default = "test-e2e-das"
  type    = string
}

data "aws_availability_zones" "available" {}

data "aws_caller_identity" "current" {}

resource "random_id" "this" {
  byte_length = 4
}

# Uncomment to use test resources
# resource "aws_kinesis_stream" "this" {
#   name             = "minimal-kinesis-stream-${random_id.this.hex}"
#   shard_count      = 1
#   retention_period = 24 # Minimum allowed retention

#   tags = {
#     Name = "${var.name}-kinesis-stream"
#   }
# }

# resource "aws_kms_key" "this" {
#   description = "Minimal KMS Key for temporary use"

#   deletion_window_in_days = 7 # Minimum allowed to make it more disposable
# }

locals {
  external_id = "external-id-${random_id.this.hex}"
}

module "stack-master" {
  source = "../terraform"

  # make sure it matches example in /quicksight/terraform/README.md
  external_id   = local.external_id
  iam_principal = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  # Uncomment to use test resources
  # kinesis_stream_arn = aws_kinesis_stream.this.arn
  # kms_key_arn        = aws_kms_key.this.arn
  # Use real resources to verify data transformation effectively
  kinesis_stream_arn = "arn:aws:kinesis:us-east-2:792169733636:stream/aws-rds-das-db-ZQO7M43PGGUXJEZVYSALTO76KA"
  kms_key_arn        = "arn:aws:kms:us-east-2:792169733636:key/f319545f-a0d4-4bfc-896f-5d37fe921ffb"
  rds_resource_id   = "arn:aws:rds:us-east-2:792169733636:db:oracle-test-data"

  template_url = local.template_url
}

output "role_arn" {
  value = module.stack-master.role_arn
}

resource "null_resource" "cluster" {
  # Make sure that assuming role success
  triggers = {
    role_arn    = module.stack-master.role_arn
    external_id = local.external_id
  }

  provisioner "local-exec" {
    # min durations = 900
    command = "aws sts assume-role --role-arn ${module.stack-master.role_arn} --role-session-name test-e2e --duration-seconds 900 --external-id ${local.external_id}"
  }
}
