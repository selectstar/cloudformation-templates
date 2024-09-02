resource "random_id" "master-identifier" {
  keepers = {
    prefix       = var.name_prefix
    ExternalId   = var.external_id
    IamPrincipal = var.iam_principal
  }
  byte_length = 8
}

resource "aws_cloudformation_stack" "stack-master" {
  name = "${var.name_prefix}-${random_id.master-identifier.hex}"

  disable_rollback = true

  parameters = {
    ExternalId   = var.external_id
    IamPrincipal = var.iam_principal
    LogGroupName = var.log_group_name
  }

  capabilities = ["CAPABILITY_IAM"]
  template_url = var.template_url
}
