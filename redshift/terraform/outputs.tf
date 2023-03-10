output "role_arn" {
  value       = aws_cloudformation_stack.stack-master.outputs.RoleArn
  description = "Identifier of AWS IAM Role intended for use by Select Star to access the Redshift cluster and logs. Needs to be shared with Select Star in adding new data source form."
}
