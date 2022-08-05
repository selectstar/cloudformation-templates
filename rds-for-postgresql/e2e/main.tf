variable "region" {
  default     = "us-east-2"
  description = "AWS region"
}

variable "name" {
  default = "test-rds-for-postgresql"
  type    = string
}

data "aws_availability_zones" "available" {}

data "aws_caller_identity" "current" {}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "3.14.2"

  name                 = var.name
  cidr                 = "10.0.0.0/16"
  azs                  = data.aws_availability_zones.available.names
  public_subnets       = ["10.0.4.0/24", "10.0.5.0/24", "10.0.6.0/24"]
  enable_dns_hostnames = true
  enable_dns_support   = true
}

resource "aws_db_subnet_group" "subnet-group" {
  name       = var.name
  subnet_ids = module.vpc.public_subnets
}

resource "aws_security_group" "security-group" {
  name   = var.name
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  lifecycle {
    # provision.py add a new ingress rules what we wanna ignore here
    ignore_changes = [
      ingress,
    ]
  }

  egress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

// E2E setup for master
resource "aws_db_parameter_group" "test-e2e-cloudformation" {
  name   = "test-e2e-cloudformation"
  family = "postgres14"

  parameter {
    name  = "log_connections"
    value = "1"
  }
}

resource "random_string" "random" {
  length  = 32
  special = false
}

resource "aws_s3_bucket" "cloudformation-bucket" {
  bucket_prefix = "e2e-test"
  acl           = "public-read"
}

resource "aws_s3_object" "cloudformation-object" {
  bucket = aws_s3_bucket.cloudformation-bucket.id

  key    = "SelectStarRDS.json"
  source = "${path.module}/../SelectStarRDS.json"
  acl    = "public-read"

  etag = filemd5("${path.module}/../SelectStarRDS.json")
}

locals {
  template_url = "https://${aws_s3_bucket.cloudformation-bucket.bucket_regional_domain_name}/${aws_s3_object.cloudformation-object.id}"
}

resource "aws_db_instance" "db-master" {
  identifier             = "${var.name}-master"
  instance_class         = "db.t3.micro"
  allocated_storage      = 5
  engine                 = "postgres"
  engine_version         = "14.2"
  username               = "edu"
  password               = random_string.random.result
  db_subnet_group_name   = aws_db_subnet_group.subnet-group.name
  vpc_security_group_ids = [aws_security_group.security-group.id]
  publicly_accessible      = true
  skip_final_snapshot      = true
  delete_automated_backups = true
  apply_immediately        = true
  backup_retention_period  = 1

  lifecycle {
    # provision.py add a new ingress rules what we wanna ignore here to aovid rollback
    ignore_changes = [
      enabled_cloudwatch_logs_exports,
    ]
  }
}
resource "random_id" "master-identifier" {
  keepers = {
    identifier = aws_db_instance.db-master.identifier
    etag       = aws_s3_object.cloudformation-object.etag
  }

  byte_length = 8
}

resource "aws_cloudformation_stack" "stack-master" {
  name = "stack-${random_id.master-identifier.hex}-${aws_db_instance.db-master.identifier}"

  disable_rollback = true

  parameters = {
    ServerName              = aws_db_instance.db-master.identifier
    Schema                  = "*.*"
    DbUser                  = aws_db_instance.db-master.username
    DbPassword              = random_string.random.result
    ProvisionAccessUserName = "selectstar-${random_id.master-identifier.hex}"
    ExternalId              = "X"
    IamPrincipal            = data.aws_caller_identity.current.account_id
    ConfigureLogging        = "true"
    ConfigureLoggingRestart = "true"
    CidrIpPrimary           = "3.23.108.85/32"
    CidrIpSecondary         = "3.20.56.105/32"
  }

  capabilities = ["CAPABILITY_IAM"]
  template_url = local.template_url
}


// E2E setup for replica
resource "aws_db_instance" "db-replica" {
  identifier               = "${var.name}-replica"
  instance_class           = "db.t3.micro"
  allocated_storage        = 5
  vpc_security_group_ids   = [aws_security_group.security-group.id]
  parameter_group_name     = aws_db_parameter_group.test-e2e-cloudformation.name
  publicly_accessible      = true
  skip_final_snapshot      = true
  delete_automated_backups = true
  backup_retention_period  = 1
  apply_immediately        = true

  replicate_source_db = aws_db_instance.db-master.id

  lifecycle {
    # provision.py add a new ingress rules what we wanna ignore here to aovid rollback
    ignore_changes = [
      enabled_cloudwatch_logs_exports,
    ]
  }
}

resource "random_id" "replica-identifier" {
  keepers = {
    identifier = aws_db_instance.db-replica.identifier
    etag       = aws_s3_object.cloudformation-object.etag
  }

  byte_length = 8
}

resource "aws_cloudformation_stack" "stack-replica" {
  name = "stack-${random_id.replica-identifier.hex}-${aws_db_instance.db-replica.identifier}"

  disable_rollback = true

  parameters = {
    ServerName              = aws_db_instance.db-replica.identifier
    Schema                  = "*.*"
    DbUser                  = aws_db_instance.db-replica.username
    DbPassword              = random_string.random.result
    ProvisionAccessUserName = "selectstar-replica-${random_id.replica-identifier.hex}"
    ExternalId              = "X"
    IamPrincipal            = data.aws_caller_identity.current.account_id
    ConfigureLogging        = "true"
    ConfigureLoggingRestart = "true"
    CidrIpPrimary           = "3.23.108.85/32"
    CidrIpSecondary         = "3.20.56.105/32"
  }

  capabilities = ["CAPABILITY_IAM"]
  template_url = local.template_url
}

## Validation
data "aws_secretsmanager_secret_version" "master" {
  secret_id = aws_cloudformation_stack.stack-master.outputs.SecretArn
}
data "aws_secretsmanager_secret_version" "replica" {
  secret_id = aws_cloudformation_stack.stack-replica.outputs.SecretArn
}
locals {
  master_username  = jsondecode(data.aws_secretsmanager_secret_version.master.secret_string)["username"]
  master_password  = jsondecode(data.aws_secretsmanager_secret_version.master.secret_string)["password"]
  replica_username = jsondecode(data.aws_secretsmanager_secret_version.replica.secret_string)["username"]
  replica_password = jsondecode(data.aws_secretsmanager_secret_version.replica.secret_string)["password"]
}

resource "null_resource" "connect-psql-master" {
  provisioner "local-exec" {
    command = "psql -c 'select 1'"
    environment = {
      PGPASSWORD = local.master_password
      PGUSER     = local.master_username
      PGDATABASE = "postgres"
      PGHOST     = aws_db_instance.db-master.address
    }
  }
}

resource "null_resource" "connect-psql-replica" {
  provisioner "local-exec" {
    command = "psql -c 'select 1'"
    environment = {
      PGPASSWORD = local.replica_password
      PGUSER     = local.replica_username
      PGDATABASE = "postgres"
      PGHOST     = aws_db_instance.db-replica.address
    }
  }
}
