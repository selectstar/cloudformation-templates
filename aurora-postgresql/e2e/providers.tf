provider "aws" {
  region              = var.region
  allowed_account_ids = ["792169733636"]

  default_tags {
    tags = {
      Component = var.name
      ManagedBy = "Terraform"
    }
  }
}
