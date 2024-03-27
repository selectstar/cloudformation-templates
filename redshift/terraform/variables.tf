variable "name_prefix" {
  type        = string
  default     = "selectstar-redshift"
  description = "AWS CloudFormation stack prefix name"
}

variable "cluster_identifier" {
  type        = string
  description = "AWS Redshift cluster identifier"
}

variable "database_grant" {
  type        = string
  default     = "*"
  description = "A comma-separated list of databases to which Select Star will be granted access. We recommend granting access to \"*\" (all existing databases) and selecting ingested database on the application side."
}

variable "provisioning_user" {
  type        = string
  nullable    = false
  description = "The Redshift username used for provisioning our Redshift user. This user is only used for provisioning new user. It is recommended to use Redshift master user."
}

variable "provisioning_database" {
  type        = string
  nullable    = false
  description = "The Redshift database used for connect to Redshift. This user is only used for provisioning new user. It can be any existing database."
}

variable "external_id" {
  type        = string
  nullable    = false
  description = "The Select Star external ID to authenticate your AWS account. It is unique for each data source and it is available in adding new data source form."
}

variable "iam_principal" {
  type        = string
  nullable    = false
  description = "The Select Star IAM principal which will have granted permission to your AWS account. This may be specific to a given data source and it is available in adding new data source form."

  validation {
    condition     = can(regex("^arn:aws:iam::", var.iam_principal))
    error_message = "Invalid IAM principal. You must enter a valid ARN."
  }
}

variable "configure_s3_logging" {
  type        = bool
  default     = true
  description = "If true and S3 logging disabled then the Redshift cluster configuration can be changed to enable S3 logging. It is recommended to set the value \"true\"."
}

variable "configure_s3_logging_restart" {
  type        = bool
  default     = true
  description = "If true and logging changes made then the Redshift cluster can be restarted to apply changes. It is recommended to set the value \"true\"."
}

variable "configure_network" {
  type = bool
  default = true
  description = "The default AWS Redshfit configuration requires the instance to be public to access metadata. If true then we verify that the Redshift instance is public and configure VPC security group rules to allow access. Do not change this parameter unless you have been specifically instructed otherwise by the support team.\n\nTo connect to an private instance, contact the support team to select the optimal connectivity solution."
}

variable "template_url" {
  type        = string
  default     = "https://select-star-production-cloudformation.s3.us-east-2.amazonaws.com/redshift/SelectStarRedshift.json"
  description = "The URL of CloudFormation Template used to provisioning integration. Don't change it unless you really know what you are doing."
}

variable "disable_rollback" {
  type = bool
  default = true
  description = "Set to false to enable rollback of the stack if stack creation failed. "
}
