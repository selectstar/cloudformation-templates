resource "random_id" "master-identifier" {
  keepers = {
    prefix     = var.name_prefix
    identifier = var.cluster_identifier
  }
  byte_length = 8
}

data "aws_redshift_cluster" "redshift" {
  cluster_identifier = var.cluster_identifier
}

resource "aws_cloudformation_stack" "stack-master" {
  name = "${var.name_prefix}-${random_id.master-identifier.hex}"

  disable_rollback = var.disable_rollback

  parameters = {
    KinesisStreamARN = var.KinesisStreamARN
    KmsKeyARN        = var.KmsKeyARN
    IamPrincipal     = var.iam_principal
    ExternalId       = var.external_id
  }

  capabilities = ["CAPABILITY_IAM"]
  template_url = var.template_url
}
