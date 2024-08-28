variable "name_prefix" {
  type        = string
  default     = "selectstar-redshift"
  description = "AWS CloudFormation stack prefix name"
}

variable "KinesisStreamARN" {
  type        = string
  validation {
    condition     = can(regex("^arn:aws:kinesis:", var.iam_principal))
    error_message = "Invalid AWS Kinesis stream. You must enter a valid ARN."
  }
}

variable "KmsKeyARN" {
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^arn:aws:kms:", var.iam_principal))
    error_message = "Invalid AWS KMS key. You must enter a valid ARN."
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
