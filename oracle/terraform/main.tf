resource "random_id" "master-identifier" {
  keepers = {
    prefix     = var.name_prefix
  }
  byte_length = 8
}


resource "aws_cloudformation_stack" "stack-master" {
  name = "${var.name_prefix}-${random_id.master-identifier.hex}"

  disable_rollback = var.disable_rollback

  parameters = {
    KinesisStreamARN = var.kinesis_stream_arn
    KmsKeyARN        = var.kms_key_arn
    IamPrincipal     = var.iam_principal
    ExternalId       = var.external_id
  }

  capabilities = ["CAPABILITY_IAM"]
  template_url = var.template_url
}
