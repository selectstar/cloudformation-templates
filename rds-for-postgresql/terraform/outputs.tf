output "role_arn" {
  value       = aws_cloudformation_stack.rds-stack.outputs.RoleArn
  description = "Identifier of AWS IAM Role intended for use by Select Star to access the RDS instance and logs. Needs to be shared with Select Star in the new data source form."
}

output "secret_arn" {
  value       = aws_cloudformation_stack.rds-stack.outputs.SecretArn
  description = "Identifier of the Secret in the AWS Secret Manager which stores the credentials for the created Select Star account in Postgresql. Needs to be shared with Select Star in the new data source form."
}
