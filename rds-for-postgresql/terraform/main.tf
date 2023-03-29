resource "random_id" "db-identifier" {
  keepers = {
    prefix = var.name_prefix
    identifier = var.db_identifier
  }
  byte_length = 8
}

data "aws_db_instance" "rds" {
  identifier = var.db_identifier
}

resource "aws_cloudformation_stack" "rds-stack" {
  name = "${var.name_prefix}-${random_id.db-identifier.hex}"

  disable_rollback = true

  parameters = {
    ServerName                = data.aws_db_instance.rds.identifier
    Schema                    = var.database_grant
    DbUser                    = var.provisioning_user
    DbPassword                = var.provisioning_user_password
    ProvisionAccessUserName   = var.access_user == "" ? "selectstar-${random_id.db-identifier.hex}" : var.access_user
    ExternalId                = var.external_id
    IamPrincipal              = var.iam_principal
    ConfigureLogging          = var.configure_cloudwatch_logging
    ConfigureLoggingRestart   = var.configure_cloudwatch_logging_restart
    CidrIpPrimary             = "3.23.108.85/32"
    CidrIpSecondary           = "3.20.56.105/32"
    SentryDsn                 = "https://14d65555628a4b6f84fcb83ef1511778@o407979.ingest.sentry.io/6639248"
  }

  capabilities = ["CAPABILITY_IAM"]
  template_url = var.template_url
}
