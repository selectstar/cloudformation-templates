# Terraform module for RDS for Postgresql integration

## Usage

For basic Terraform module usage, refer to Terraform tutorial "[Reuse Configuration with Modules](https://developer.hashicorp.com/terraform/tutorials/modules)".

Please use [Select Star Panel](https://app.selectstar.com/) to get the correct values of authorization parameters `iam_principal` and `external_id`.

Example snippet usage:

```terraform
module "stack" {
  source = "github.com/selectstar/cloudformation-templates//rds-for-postgresql/terraform"

  db_identifier               = "X"       # set to your RDS DB identifier, eg. aws_db_instance.db-master.identifier
  provisioning_user           = "awsuser" # set to provisioning user, master user preferred, eg. aws_db_instance.db-master.username
  provisioning_user_password  = var.provisioning_user_password  # set to the password for the `provisioning_user`
  external_id                 = "X"       # available in add new data source form
  iam_principal               = "X"       # available in add new data source form
}

variable "provisioning_user_password" {
  type          = string
  sensitive     = true
}
```

Once the module is provisioned, you need to share output `role_arn` (eg. use `module.stack.role_arn`) with Select Star.

## Update docs

To update Terraform documentation use [terraform-docs](https://terraform-docs.io/) with the command:

```
terraform-docs markdown . --output-file README.md
```

<!-- BEGIN_TF_DOCS -->
## Requirements

No requirements.

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | n/a |
| <a name="provider_random"></a> [random](#provider\_random) | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_cloudformation_stack.rds-stack](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudformation_stack) | resource |
| [random_id.db-identifier](https://registry.terraform.io/providers/hashicorp/random/latest/docs/resources/id) | resource |
| [aws_db_instance.rds](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/db_instance) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_access_user"></a> [access\_user](#input\_access\_user) | The Postgresql username created for accessing the db. A "selectstar-" prefixed username is generated automatically if unspecified. | `string` | `""` | no |
| <a name="input_configure_cloudwatch_logging"></a> [configure\_cloudwatch\_logging](#input\_configure\_cloudwatch\_logging) | If true and CloudWatch logging is disabled, then the RDS instance configuration will be changed to enable CloudWatch logging. It is recommended to set the value "true". | `bool` | `true` | no |
| <a name="input_configure_cloudwatch_logging_restart"></a> [configure\_cloudwatch\_logging\_restart](#input\_configure\_cloudwatch\_logging\_restart) | If true and logging changes are made, then the RDS instance can be restarted to apply changes. It is recommended to set the value "true". | `bool` | `true` | no |
| <a name="input_database_grant"></a> [database\_grant](#input\_database\_grant) | A comma-separated list of databases to which Select Star will be granted access. We recommend granting access to "*.*" (all existing databases) and selecting ingested database on the application side. | `string` | `"*.*"` | no |
| <a name="input_db_identifier"></a> [db\_identifier](#input\_db\_identifier) | AWS RDS DB identifier | `string` | n/a | yes |
| <a name="input_disable_rollback"></a> [disable\_rollback](#input\_disable\_rollback) | Set to false to enable rollback of the stack if stack creation failed. | `bool` | `true` | no |
| <a name="input_external_id"></a> [external\_id](#input\_external\_id) | The Select Star external ID to authenticate your AWS account. It is unique for each data source and it is available in adding new data source form. | `string` | n/a | yes |
| <a name="input_iam_principal"></a> [iam\_principal](#input\_iam\_principal) | The Select Star IAM principal which will have granted permission to your AWS account. This may be specific to a given data source and it is available in adding new data source form. | `string` | n/a | yes |
| <a name="input_name_prefix"></a> [name\_prefix](#input\_name\_prefix) | AWS CloudFormation stack prefix name | `string` | `"selectstar-rds-postgresql"` | no |
| <a name="input_provisioning_user"></a> [provisioning\_user](#input\_provisioning\_user) | The Postgresql username used for provisioning our Postgresql user. This user is only used for provisioning new user. It is recommended to use the Postgresql root user. | `string` | n/a | yes |
| <a name="input_provisioning_user_password"></a> [provisioning\_user\_password](#input\_provisioning\_user\_password) | The password for the provisioning\_user. This is only used for provisioning a new user during initial setup. | `string` | n/a | yes |
| <a name="input_template_url"></a> [template\_url](#input\_template\_url) | The URL of CloudFormation Template used to provisioning integration. Don't change it unless you really know what you are doing. | `string` | `"https://select-star-production-cloudformation.s3.us-east-2.amazonaws.com/rds-for-postgresql/SelectStarRDS.json"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_role_arn"></a> [role\_arn](#output\_role\_arn) | Identifier of AWS IAM Role intended for use by Select Star to access the RDS instance and logs. Needs to be shared with Select Star in the new data source form. |
| <a name="output_secret_arn"></a> [secret\_arn](#output\_secret\_arn) | Identifier of the Secret in the AWS Secret Manager which stores the credentials for the created Select Star account in Postgresql. Needs to be shared with Select Star in the new data source form. |
<!-- END_TF_DOCS -->
