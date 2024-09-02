
resource "aws_s3_bucket" "cloudformation-bucket" {
  bucket_prefix = "e2e-test"
}

resource "aws_s3_object" "cloudformation-object" {
  bucket = aws_s3_bucket.cloudformation-bucket.id

  key    = "SelectStarOracle.json"
  content = jsonencode(yamldecode(file("${path.module}/../SelectStarOracle.yaml")))

  etag = filemd5("${path.module}/../SelectStarOracle.yaml")
}

locals {
  template_url = "https://${aws_s3_bucket.cloudformation-bucket.bucket_regional_domain_name}/${aws_s3_object.cloudformation-object.id}"
}
