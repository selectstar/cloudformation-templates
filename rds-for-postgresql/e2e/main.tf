variable "region" {
  default     = "eu-central-1"
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

  lifecycle {
    # provision.py add a new ingress rules what we wanna ignore here
    ignore_changes = [
      ingress,
    ]
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
}

resource "aws_s3_bucket_acl" "cloudformation-bucket" {
  bucket = aws_s3_bucket.cloudformation-bucket.id
  acl    = "public-read"
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
  identifier               = "${var.name}-master"
  instance_class           = "db.t3.micro"
  allocated_storage        = 5
  engine                   = "postgres"
  engine_version           = "14.2"
  username                 = "edu"
  password                 = random_string.random.result
  db_subnet_group_name     = aws_db_subnet_group.subnet-group.name
  vpc_security_group_ids   = [aws_security_group.security-group.id]
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

module "stack-master" {
  source = "../terraform"

  # make sure it matches the example in /rds-for-postgresql/terraform/README.md
  db_identifier = aws_db_instance.db-master.identifier
  external_id   = "X"
  iam_principal = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"

  template_url = local.template_url

  depends_on = [
    aws_db_instance.db-master
  ]
}

data "http" "myip" {
  url = "http://ipv4.icanhazip.com"
}

resource "aws_security_group_rule" "example" {
  type              = "ingress"
  from_port         = aws_db_instance.db-master.port
  to_port           = aws_db_instance.db-master.port
  protocol          = "tcp"
  cidr_blocks       = ["${chomp(data.http.myip.response_body)}/32"]
  security_group_id = aws_security_group.security-group.id
  depends_on = [
    module.stack-master,
    module.stack-replica
  ]
}

# TODO: Validate assume role & access to AWS CloudWatch
