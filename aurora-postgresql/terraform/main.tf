resource "random_id" "db-identifier" {
  keepers = {
    prefix     = var.name_prefix
    identifier = var.db_identifier
  }
  byte_length = 8
}

data "aws_rds_cluster" "rds" {
  cluster_identifier = var.db_identifier
}

resource "aws_cloudformation_stack" "rds-stack" {
  name = "${var.name_prefix}-${random_id.db-identifier.hex}"

  disable_rollback = var.disable_rollback

  parameters = {
    ClusterName  = data.aws_rds_cluster.rds.cluster_identifier
    ExternalId   = var.external_id
    IamPrincipal = var.iam_principal
  }

  capabilities = ["CAPABILITY_IAM"]
  template_url = var.template_url
}
