variable "region" {
  default     = "eu-central-1"
  description = "AWS region"
}

variable "name" {
  default = "test-e2e-oracle"
  type    = string
}

data "aws_availability_zones" "available" {}

data "aws_caller_identity" "current" {}

module "stack-master" {
  source = "../terraform"

  # make sure it matches example in /quicksight/terraform/README.md
  external_id   = "X"
  iam_principal = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  # TODO: create them on-demand
  KinesisStreamARN = "arn:aws:kinesis:us-east-2:792169733636:stream/aws-rds-das-db-UP7H5HCH5M6GDWPOIZJ4ZFJQNY"
  KmsKeyARN = "arn:aws:kms:us-east-2:792169733636:key/e6a87da6-b7fd-44d9-aa21-66bcec829832"

  template_url = local.template_url
}

output "role_arn" {
  value = module.stack-master.role_arn
}

resource "null_resource" "cluster" {
  # Make sure that assuming role success
  triggers = {
    role_arn    = module.stack-master.role_arn
    external_id = module.stack-master.external_id
  }

  provisioner "local-exec" {
    # min durations = 900
    command = "aws sts assume-role --role-arn ${module.stack-master.role_arn} --role-session-name test-e2e --duration-seconds 900 --external-id ${module.stack-master.external_id}"
  }
}
