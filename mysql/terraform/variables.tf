variable "name_prefix" {
  type        = string
  default     = "selectstar-mysql"
  description = "AWS CloudFormation stack prefix name"
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

variable "template_url" {
  type        = string
  default     = "https://select-star-production-cloudformation.s3.us-east-2.amazonaws.com/mysql/SelectStarMySQL.json"
  description = "The URL of CloudFormation Template used to provisioning integration. Don't change it unless you really know what you are doing."
}
