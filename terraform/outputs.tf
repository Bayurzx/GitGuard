output "lambda_function_arn" {
  description = "The ARN of the Lambda function"
  value       = aws_lambda_function.github_backup.arn
}

output "backup_bucket_name" {
  description = "The name of the S3 backup bucket"
  value       = aws_s3_bucket.backup_bucket.id
}

output "secrets_manager_arn" {
  description = "The ARN of the Secrets Manager secret"
  value       = aws_secretsmanager_secret.github_credentials.arn
}