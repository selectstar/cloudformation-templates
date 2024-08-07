variable "region" {
  default     = "eu-central-1"
  description = "AWS region"
}

variable "name" {
  default = "test-e2e-redshift"
  type    = string
}

variable "configure_network" { ## Flag for test case
  default = true
  type    = bool
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

resource "aws_subnet" "subnet" {
  cidr_block = "10.0.7.0/24"
  vpc_id     = module.vpc.vpc_id

  tags = {
    Name = var.name
  }
}

resource "aws_redshift_subnet_group" "subnet_group" {
  name       = var.name
  subnet_ids = [aws_subnet.subnet.id]
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
resource "aws_redshift_cluster" "e2e" {
  cluster_identifier                  = "test-e2e-cloudformation"
  database_name                       = "mydb"
  master_username                     = "root"
  master_password                     = random_string.random.result
  node_type                           = "dc2.large"
  cluster_type                        = "single-node"
  automated_snapshot_retention_period = 0
  skip_final_snapshot                 = true
  cluster_subnet_group_name           = aws_redshift_subnet_group.subnet_group.name
  publicly_accessible                 = var.configure_network
  lifecycle {
    # provision.py add a new ingress rules what we wanna ignore here
    ignore_changes = [
      logging,
    ]
  }
}

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

  key    = "SelectStarRedshift.json"
  source = "${path.module}/../SelectStarRedshift.json"

  etag = filemd5("${path.module}/../SelectStarRedshift.json")
}

locals {
  template_url = "https://${aws_s3_bucket.cloudformation-bucket.bucket_regional_domain_name}/${aws_s3_object.cloudformation-object.id}"
}



resource "random_id" "master-identifier" {
  keepers = {
    identifier = aws_redshift_cluster.e2e.cluster_identifier
    etag       = aws_s3_object.cloudformation-object.etag
  }

  byte_length = 8
}

module "stack-master" {
  source = "../terraform"

  # make sure it matches example in /redshift/terraform/README.md
  cluster_identifier    = aws_redshift_cluster.e2e.cluster_identifier
  provisioning_user     = aws_redshift_cluster.e2e.master_username
  provisioning_database = aws_redshift_cluster.e2e.database_name
  external_id           = "X"
  iam_principal         = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  configure_network     = var.configure_network
  template_url          = local.template_url

  depends_on = [
    aws_redshift_cluster.e2e
  ]
}

module "stack-configurationless" {
  source = "../terraform"

  cluster_identifier           = aws_redshift_cluster.e2e.cluster_identifier
  provisioning_user            = aws_redshift_cluster.e2e.master_username
  provisioning_database        = aws_redshift_cluster.e2e.database_name
  # for already configured cluster, we may skip the logging configuration
  configure_s3_logging         = false
  configure_s3_logging_restart = false
  external_id                  = "X"
  iam_principal                = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  configure_network            = var.configure_network
  template_url                 = local.template_url

  depends_on = [
    module.stack-master
  ]
}


data "http" "myip" {
  url = "http://ipv4.icanhazip.com"
}

## Validation
resource "aws_redshiftdata_statement" "example" {
  cluster_identifier = aws_redshift_cluster.e2e.cluster_identifier
  database           = aws_redshift_cluster.e2e.database_name
  db_user            = "selectstar"
  sql                = "SELECT 1"

  depends_on = [
    module.stack-master
  ]
}

output "role_arn" {
  value = module.stack-master.role_arn
}
