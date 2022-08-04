# E2E tests for CloudFormation template for AWS for PostgreSQL integration

These tests are intended to verify the E2E of the CloudFormation template. During their operation, the infrastructure is created and then the CloudFormation stack is created.

## Requirements

* Access to AWS account
* Terraform pre-installed

## Usage

Initialize Terraform (eg. create state file):

```bash
terraform init
```

Starts tests (eg. create state file):

```bash
terraform apply
```

After testing, be sure to delete resources:

```bash
terraform destroy
terraform destroy
```

If the removal of CloudFormation Stack fails, it is worth restarting the operation, because then the stack is deleted without the problematic resources (most likely due to the impossibility of correct `LambdaFunction` execution).