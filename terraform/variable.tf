variable "lambda_image_uri" {
  description = "The URI of the Lambda container image in ECR"
  type        = string
}

variable "lambda_github_org" {
  description = "The github org owner to read and process"
  type        = string
}

variable "s3_bucket_name" {
  description = "The name of the S3 bucket for backup"
  type        = string
}

variable "github_secret_name" {
  description = "The name of the Secrets Manager secret for GitHub credentials"
  type        = string
}

variable "home_tmp_dir" {
  description = "The Git CLI expects the $HOME environment variable to be set, as it uses $HOME/.gitconfig for authentication and configuration. This is the writable directory in Lambda's runtime environment."
  type        = string
}

variable "common_tags" {
  description = "Common tags to be applied to all resources"
  type        = map(string)
  default = {
    Environment = "production"
    Project     = "github-backup"
    ManagedBy   = "terraform"
  }
}
