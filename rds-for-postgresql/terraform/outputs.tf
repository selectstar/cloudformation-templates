output "role_arn" {
  value       = aws_cloudformation_stack.rds-stack.outputs.RoleArn
  description = "Identifier of AWS IAM Role intended for use by Select Star to access the RDS instance and logs. Needs to be shared with Select Star in the new data source form."
}
