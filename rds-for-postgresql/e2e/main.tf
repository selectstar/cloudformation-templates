provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Component = var.name
      ManagedBy = "Terraform"
    }
  }
}

variable "region" {
  default     = "us-east-2"
  description = "AWS region"
}

variable "name" {
  default = "test-e2e-cloudformation-rds-for-postgresql"
  type    = string
}

resource "random_string" "random" {
  length = 32
  special = false
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

  egress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# resource "aws_db_parameter_group" "test-e2e-cloudformation" {
#   name   = "test-e2e-cloudformation"
#   family = "postgres13"

#   parameter {
#     name  = "log_connections"
#     value = "1"
#   }
# }

resource "aws_db_instance" "db-instance" {
  identifier             = var.name
  instance_class         = "db.t3.micro"
  allocated_storage      = 5
  engine                 = "postgres"
  engine_version         = "14.2"
  username               = "edu"
  password               = random_string.random.result
  db_subnet_group_name   = aws_db_subnet_group.subnet-group.name
  vpc_security_group_ids = [aws_security_group.security-group.id]
  #   parameter_group_name   = aws_db_parameter_group.test-e2e-cloudformation.name
  publicly_accessible = true
  skip_final_snapshot = true
}

resource "aws_cloudformation_stack" "stack" {
  name = var.name

  disable_rollback = true

  parameters = {
    ServerName              = aws_db_instance.db-instance.identifier
    Schema                  = "*.*"
    DbUser                  = aws_db_instance.db-instance.username
    DbPassword              = aws_db_instance.db-instance.password
    ProvisionAccessUserName = "selectstar"
    ExternalId              = "X"
    IamPrincipal            = data.aws_caller_identity.current.account_id
    ConfigureLogging        = "true"
    ConfigureLoggingRestart = "true"
    CidrIpPrimary           = "3.23.108.85/32"
    CidrIpSecondary         = "3.20.56.105/32"
  }

  capabilities = ["CAPABILITY_IAM"]
  template_body = file("${path.module}/../SelectStarRDS.json")
}
