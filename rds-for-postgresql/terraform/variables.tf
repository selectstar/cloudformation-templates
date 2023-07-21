variable "name_prefix" {
  type        = string
  default     = "selectstar-rds-postgresql"
  description = "AWS CloudFormation stack prefix name"
}

variable "db_identifier" {
  type        = string
  description = "AWS RDS DB identifier"
}

variable "database_grant" {
  type        = string
  default     = "*.*"
  description = "A comma-separated list of databases to which Select Star will be granted access. We recommend granting access to \"*.*\" (all existing databases) and selecting ingested database on the application side."
}

variable "provisioning_user" {
  type        = string
  nullable    = false
  description = "The Postgresql username used for provisioning our Postgresql user. This user is only used for provisioning new user. It is recommended to use the Postgresql root user."
}

variable "provisioning_user_password" {
  type        = string
  sensitive   = true
  nullable    = false
  description = "The password for the provisioning_user. This is only used for provisioning a new user during initial setup."
}

variable "access_user" {
  type        = string
  nullable    = false
  default     = ""
  description = "The Postgresql username created for accessing the db. A \"selectstar-\" prefixed username is generated automatically if unspecified."
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

variable "configure_cloudwatch_logging" {
  type        = bool
  default     = true
  description = "If true and CloudWatch logging is disabled, then the RDS instance configuration will be changed to enable CloudWatch logging. It is recommended to set the value \"true\"."
}

variable "configure_cloudwatch_logging_restart" {
  type        = bool
  default     = true
  description = "If true and logging changes are made, then the RDS instance can be restarted to apply changes. It is recommended to set the value \"true\"."
}

variable "template_url" {
  type        = string
  default     = "https://select-star-production-cloudformation.s3.us-east-2.amazonaws.com/rds-for-postgresql/SelectStarRDS.json"
  description = "The URL of CloudFormation Template used to provisioning integration. Don't change it unless you really know what you are doing."
}

variable "disable_rollback" {
  type = bool
  default = true
  description = "Set to false to enable rollback of the stack if stack creation failed. "
}
