# Terraform module for DAS integration

## Usage

For basic Terraform module usage, refer to Terraform tutorial "[Reuse Configuration with Modules](https://developer.hashicorp.com/terraform/tutorials/modules)".

Please use [Select Star Panel](https://app.selectstar.com/) to get the correct values of authorization parameters `iam_principal` and `external_id`.

Example snippet usage:

```terraform
module "stack" {
  source = "github.com/selectstar/cloudformation-templates//das/terraform"

  kinesis_stream_arn = "arn:aws:kinesis:us-east-2:792169733636:stream/aws-rds-das-db-ZQO7M43PGGUXJEZVYSALTO76KA"
  kms_key_arn        = "arn:aws:kms:us-east-2:792169733636:key/f319545f-a0d4-4bfc-896f-5d37fe921ffb"
  rds_resource_id    = "db-ZQO7M43PGGUXJEZVYSALTO76KA"

  external_id        = "X" # available in add new data source form
  iam_principal      = "X" # available in add new data source form
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

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_disable_rollback"></a> [disable\_rollback](#input\_disable\_rollback) | Set to false to enable rollback of the stack if stack creation failed. | `bool` | `true` | no |
| <a name="input_external_id"></a> [external\_id](#input\_external\_id) | The Select Star external ID to authenticate your AWS account. It is unique for each data source and it is available in adding new data source form. | `string` | n/a | yes |
| <a name="input_iam_principal"></a> [iam\_principal](#input\_iam\_principal) | The Select Star IAM principal which will have granted permission to your AWS account. This may be specific to a given data source and it is available in adding new data source form. | `string` | n/a | yes |
| <a name="input_kinesis_stream_arn"></a> [kinesis\_stream\_arn](#input\_kinesis\_stream\_arn) | n/a | `string` | n/a | yes |
| <a name="input_kms_key_arn"></a> [kms\_key\_arn](#input\_kms\_key\_arn) | n/a | `string` | n/a | yes |
| <a name="input_name_prefix"></a> [name\_prefix](#input\_name\_prefix) | AWS CloudFormation stack prefix name | `string` | `"selectstar-das"` | no |
| <a name="input_rds_resource_id"></a> [rds\_resource\_arn](#input\_rds\_resource\_arn) | The RDS resource ARN that you want to integrate with Select Star. It is available in the RDS console. | `string` | n/a | yes |
| <a name="input_template_url"></a> [template\_url](#input\_template\_url) | The URL of CloudFormation Template used to provisioning integration. Don't change it unless you really know what you are doing. | `string` | `"https://select-star-production-cloudformation.s3.us-east-2.amazonaws.com/das/SelectStarDAS.json"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_role_arn"></a> [role\_arn](#output\_role\_arn) | Identifier of AWS IAM Role intended for use by Select Star to access the AWS S3 bucket. Needs to be shared with Select Star in adding new data source form. |
<!-- END_TF_DOCS -->
