
resource "aws_s3_bucket" "cloudformation-bucket" {
  bucket_prefix = "e2e-test"
}

resource "aws_s3_object" "cloudformation-object" {
  bucket = aws_s3_bucket.cloudformation-bucket.id

  key    = "SelectStarDAS.json"
  content = jsonencode(yamldecode(file("${path.module}/../SelectStarDAS.yaml")))

  etag = filemd5("${path.module}/../SelectStarDAS.yaml")
}

locals {
  template_url = "https://${aws_s3_bucket.cloudformation-bucket.bucket_regional_domain_name}/${aws_s3_object.cloudformation-object.id}"
}
