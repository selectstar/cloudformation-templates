# Terraform module for Redshift integration

## Usage

For basic Terraform module usage, refer to Terraform tutorial "[Reuse Configuration with Modules](https://developer.hashicorp.com/terraform/tutorials/modules)".

Please use [Select Star Panel](https://app.selectstar.com/) to get the correct values of authorization parameters `iam_principal` and `external_id`.

Example snippet usage:

```terraform
module "stack" {
  source = "github.com/selectstar/cloudformation-templates//redshift/terraform"

  cluster_identifier    = "X" # set to your Redshift cluster identifier, eg. aws_redshift_cluster.primary.cluster_identifier
  provisioning_user     = "awsuser" # set to provisioning user, master user preferred, eg. aws_redshift_cluster.primary.master_username
  provisioning_database = "dev" # set to database to connect to Redshift, eg. aws_redshift_cluster.primary.database_name
  external_id           = "X" # available in add new data source form
  iam_principal         = "X" # available in add new data source form
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
| [aws_cloudformation_stack.stack-master](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudformation_stack) | resource |
| [random_id.master-identifier](https://registry.terraform.io/providers/hashicorp/random/latest/docs/resources/id) | resource |
| [aws_redshift_cluster.redshift](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/redshift_cluster) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_cluster_identifier"></a> [cluster\_identifier](#input\_cluster\_identifier) | AWS Redshift cluster identifier | `string` | n/a | yes |
| <a name="input_configure_s3_logging"></a> [configure\_s3\_logging](#input\_configure\_s3\_logging) | If true and S3 logging disabled then the Redshift cluster configuration can be changed to enable S3 logging. It is recommended to set the value "true". | `bool` | `true` | no |
| <a name="input_configure_s3_logging_restart"></a> [configure\_s3\_logging\_restart](#input\_configure\_s3\_logging\_restart) | If true and logging changes made then the Redshift cluster can be restarted to apply changes. It is recommended to set the value "true". | `bool` | `true` | no |
| <a name="input_database_grant"></a> [database\_grant](#input\_database\_grant) | A comma-separated list of databases to which Select Star will be granted access. We recommend granting access to "*" (all existing databases) and selecting ingested database on the application side. | `string` | `"*"` | no |
| <a name="input_disable-rollback"></a> [disable-rollback](#input\_disable-rollback) | Set to false to enable rollback of the stack if stack creation failed. | `bool` | `true` | no |
| <a name="input_external_id"></a> [external\_id](#input\_external\_id) | The Select Star external ID to authenticate your AWS account. It is unique for each data source and it is available in adding new data source form. | `string` | n/a | yes |
| <a name="input_iam_principal"></a> [iam\_principal](#input\_iam\_principal) | The Select Star IAM principal which will have granted permission to your AWS account. This may be specific to a given data source and it is available in adding new data source form. | `string` | n/a | yes |
| <a name="input_name_prefix"></a> [name\_prefix](#input\_name\_prefix) | AWS CloudFormation stack prefix name | `string` | `"selectstar-redshift"` | no |
| <a name="input_provisioning_database"></a> [provisioning\_database](#input\_provisioning\_database) | The Redshift database used for connect to Redshift. This user is only used for provisioning new user. It can be any existing database. | `string` | n/a | yes |
| <a name="input_provisioning_user"></a> [provisioning\_user](#input\_provisioning\_user) | The Redshift username used for provisioning our Redshift user. This user is only used for provisioning new user. It is recommended to use Redshift master user. | `string` | n/a | yes |
| <a name="input_template_url"></a> [template\_url](#input\_template\_url) | The URL of CloudFormation Template used to provisioning integration. Don't change it unless you really know what you are doing. | `string` | `"https://select-star-production-cloudformation.s3.us-east-2.amazonaws.com/redshift/SelectStarRedshift.json"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_role_arn"></a> [role\_arn](#output\_role\_arn) | Identifier of AWS IAM Role intended for use by Select Star to access the Redshift cluster and logs. Needs to be shared with Select Star in adding new data source form. |
<!-- END_TF_DOCS -->
