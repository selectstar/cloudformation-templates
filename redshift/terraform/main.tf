resource "random_id" "master-identifier" {
  keepers = {
    prefix = var.name_prefix
    identifier = var.cluster_identifier
  }
  byte_length = 8
}

data "aws_redshift_cluster" "redshift" {
  cluster_identifier = var.cluster_identifier
}

resource "aws_cloudformation_stack" "stack-master" {
  name = "${var.name_prefix}-${random_id.master-identifier.hex}"

  disable_rollback = var.disable-rollback

  parameters = {
    Cluster                   = data.aws_redshift_cluster.redshift.cluster_identifier
    Grant                     = var.database_grant
    Db                        = var.provisioning_database
    ExternalId                = var.external_id
    DbUser                    = var.provisioning_user
    IamPrincipal              = var.iam_principal
    CidrIpPrimary             = "3.23.108.85/32"
    CidrIpSecondary           = "3.20.56.105/32"
    ConfigureS3Logging        = var.configure_s3_logging
    ConfigureS3LoggingRestart = var.configure_s3_logging_restart
    SentryDsn                 = "https://14d65555628a4b6f84fcb83ef1511778@o407979.ingest.sentry.io/6639248"
  }

  capabilities = ["CAPABILITY_IAM"]
  template_url = var.template_url
}
