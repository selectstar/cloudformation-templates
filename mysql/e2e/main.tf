variable "region" {
  default     = "eu-central-1"
  description = "AWS region"
}

variable "name" {
  default = "test-e2e-mysql"
  type    = string
}

data "aws_availability_zones" "available" {}

data "aws_caller_identity" "current" {}


resource "random_string" "random" {
  length  = 32
  special = false
}

resource "aws_s3_bucket" "cloudformation-bucket" {
  bucket_prefix = "e2e-test"
}

resource "aws_s3_bucket_ownership_controls" "cloudformation-bucket" {
  bucket = aws_s3_bucket.cloudformation-bucket.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_object" "cloudformation-object" {
  bucket = aws_s3_bucket.cloudformation-bucket.id

  key    = "SelectStarMySQL.json"
  source = "${path.module}/../SelectStarMySQL.json"

  etag = filemd5("${path.module}/../SelectStarMySQL.json")
}

locals {
  template_url = "https://${aws_s3_bucket.cloudformation-bucket.bucket_regional_domain_name}/${aws_s3_object.cloudformation-object.id}"
  external_id  = "external-id"
}

resource "random_id" "master-identifier" {
  keepers = {
    etag = aws_s3_object.cloudformation-object.etag
  }

  byte_length = 8
}

module "stack-master" {
  source = "../terraform"

  # make sure it matches example in /mysql/terraform/README.md
  external_id   = local.external_id
  iam_principal = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"

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
