terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.0.0"
}

# Lambda function and required resources
resource "aws_lambda_function" "github_backup" {
  function_name = "github-backup-function"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = var.lambda_image_uri

  timeout     = 900 # 15 minutes
  memory_size = 2048

  environment {
    variables = {
      SECRET_NAME = aws_secretsmanager_secret.github_credentials.name
      GITHUB_ORG  = var.lambda_github_org
      S3_BUCKET   = aws_s3_bucket.backup_bucket.id
    }
  }

  tags = var.common_tags
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "github-backup-lambda-role"
  path = "/service-role/" # logically group roles by different categories like a folder

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.common_tags
}

# Policy for Lambda to access S3, Secrets Manager, and CloudWatch Logs
resource "aws_iam_role_policy" "lambda_policy" {
  name = "github-backup-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:CreateBucket" # Added for bucket creation if needed
        ]
        Resource = [
          aws_s3_bucket.backup_bucket.arn,
          "${aws_s3_bucket.backup_bucket.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.github_credentials.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# S3 bucket for backups
resource "aws_s3_bucket" "backup_bucket" {
  bucket = var.s3_bucket_name

  tags = var.common_tags
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backup_bucket_encryption" {
  bucket = aws_s3_bucket.backup_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backup_lifecycle" {
  bucket = aws_s3_bucket.backup_bucket.id

  rule {
    id     = "archive-backups"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "DEEP_ARCHIVE"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "backup_bucket_access" {
  bucket = aws_s3_bucket.backup_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}



# Secret for GitHub credentials
resource "aws_secretsmanager_secret" "github_credentials" {
  name = var.github_secret_name

  tags = var.common_tags

}

# EventBridge rule for scheduled execution
resource "aws_cloudwatch_event_rule" "github_backup" {
  name                = "github-backup-schedule"
  description         = "Trigger GitHub backup Lambda function every Sunday at 2 PM UTC"
  schedule_expression = "cron(0 14 ? * 1 *)" # Every Sunday at 2 PM UTC

  tags = var.common_tags
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.github_backup.name
  target_id = "GithubBackupLambda"
  arn       = aws_lambda_function.github_backup.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.github_backup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.github_backup.arn
}

# Get current AWS region and account ID
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}