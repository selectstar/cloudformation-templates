variable "name_prefix" {
  type        = string
  default     = "selectstar-das"
  description = "AWS CloudFormation stack prefix name"
}

variable "kinesis_stream_arn" {
  type        = string
  validation {
    condition     = can(regex("^arn:aws:kinesis:", var.kinesis_stream_arn))
    error_message = "Invalid AWS Kinesis stream. You must enter a valid ARN."
  }
}

variable "kms_key_arn" {
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^arn:aws:kms:", var.kms_key_arn))
    error_message = "Invalid AWS KMS key. You must enter a valid ARN."
  }
}

variable "rds_resource_id" {
  type        = string
  nullable    = false
  description = "The RDS resource ID that you want to integrate with Select Star. It is available in the RDS console."

  validation {
    condition     = can(regex("^[A-Z0-9\\-]+$", var.rds_resource_id))
    error_message = "Invalid RDS resource ID. You must enter a valid resource ID. Are you sure you didn't use resource ARN? "
  }
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
variable "external_id" {
  type        = string
  nullable    = false
  description = "The Select Star external ID to authenticate your AWS account. It is unique for each data source and it is available in adding new data source form."
}

variable "disable_rollback" {
  type = bool
  default = true
  description = "Set to false to enable rollback of the stack if stack creation failed. "
}

variable "template_url" {
  type        = string
  default     = "https://select-star-production-cloudformation.s3.us-east-2.amazonaws.com/das/SelectStarDAS.json"
  description = "The URL of CloudFormation Template used to provisioning integration. Don't change it unless you really know what you are doing."
}
