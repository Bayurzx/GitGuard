# GitHub Organization Backup System

An automated backup solution for GitHub organizations using AWS Lambda, S3, and Terraform. This system creates comprehensive backups of repositories, metadata, and wikis on a weekly schedule.

## 🏗️ Architecture

The system uses a containerized AWS Lambda function to orchestrate backups, storing data in S3 with intelligent lifecycle management. See [Architecture Documentation](./ARCHITECTURE.md) for detailed technical specifications.

## ✨ Features

- **Complete Repository Backup**: Full git mirrors with all branches and history
- **Metadata Preservation**: Issues, pull requests, releases, labels, milestones, and more
- **Wiki Backup**: Repository wikis backed up separately
- **Automated Scheduling**: Weekly execution every Sunday at 2 PM UTC
- **Cost Optimization**: Automatic transition to Deep Archive after 90 days
- **Security**: Credentials stored in AWS Secrets Manager, encrypted S3 storage
- **Monitoring**: CloudWatch logging and metrics

## 📋 Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform >= 1.0.0
- Docker for building Lambda container
- GitHub Personal Access Token with organization access

## 🚀 Quick Start

### 1. Configure Secrets

Create a secret in AWS Secrets Manager with the following structure:

```json
{
  "GITHUB_TOKEN": "ghp_your_github_token_here",
  "AWS_ACCESS_KEY_ID": "your_aws_access_key",
  "AWS_SECRET_ACCESS_KEY": "your_aws_secret_key",
  "AWS_REGION": "us-east-1"
}
```

### 2. Build and Push Container

```bash
# Build the Lambda container
docker build -t github-backup-lambda .

# Tag for ECR (replace with your ECR URI)
docker tag github-backup-lambda:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/github-backup:latest

# Push to ECR
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/github-backup:latest
```

### 3. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var="lambda_image_uri=123456789012.dkr.ecr.us-east-1.amazonaws.com/github-backup:latest"

# Apply configuration
terraform apply
```

## ⚙️ Configuration

### Terraform Variables

Create a `terraform.tfvars` file:

```hcl
# Required
lambda_image_uri = "123456789012.dkr.ecr.us-east-1.amazonaws.com/github-backup:latest"
lambda_github_org = "your-github-org"
s3_bucket_name = "your-backup-bucket-name"
github_secret_name = "github-backup-credentials"

# Optional
home_tmp_dir = "/tmp"
common_tags = {
  Environment = "production"
  Project     = "github-backup"
  Owner       = "devops-team"
}
```

### Environment Variables

The Lambda function uses these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `GITHUB_ORG` | GitHub organization name | `mycompany` |
| `S3_BUCKET` | S3 bucket for backups | `mycompany-github-backups` |
| `SECRET_NAME` | Secrets Manager secret name | `github-backup-credentials` |
| `HOME` | Home directory for Git operations | `/tmp` |

## 📁 Backup Structure

Backups are organized in S3 as follows:

```
s3://your-backup-bucket/
├── repository-1/
│   ├── git_backup_2025-01-15.tar.gz
│   ├── wiki_backup_2025-01-15.tar.gz
│   └── metadata/
│       ├── repository-1_issues.json
│       ├── repository-1_releases.json
│       ├── repository-1_pull_requests.json
│       └── ...
├── repository-2/
│   └── ...
```

## 🔒 Security Features

- **Encrypted Storage**: S3 server-side encryption (AES-256)
- **Access Control**: IAM roles with minimal required permissions
- **Secret Management**: GitHub tokens stored in AWS Secrets Manager
- **Network Security**: Public access blocked on S3 bucket
- **Audit Trail**: CloudWatch logs for all operations

## 📊 Monitoring

### CloudWatch Metrics

Monitor these key metrics:

- Lambda execution duration
- Memory utilization
- Error rates
- S3 upload success

### Log Analysis

Search CloudWatch logs for:

```
# Successful backups
"Backup completed successfully"

# Failed operations
ERROR

# Specific repository issues
"Failed to backup" AND "repository-name"
```

## 🛠️ Maintenance

### Regular Tasks

1. **Monitor Backup Health**: Check CloudWatch dashboards weekly
2. **Review Storage Costs**: Analyze S3 usage monthly
3. **Token Rotation**: Update GitHub tokens before expiration
4. **Test Restores**: Perform quarterly restore tests

### Troubleshooting

#### Common Issues

**Lambda Timeout**
- Reduce repository count per execution
- Increase timeout (max 15 minutes)
- Optimize compression settings

**API Rate Limits**
- GitHub API allows 5000 requests/hour
- Function includes rate limit handling
- Consider implementing exponential backoff

**Storage Issues**
- Monitor ephemeral storage usage (10GB limit)
- Clean up temporary files between repositories
- Check S3 permissions

## 🔄 Disaster Recovery

### Backup Verification

```bash
# List recent backups
aws s3 ls s3://your-backup-bucket/ --recursive --human-readable

# Download specific backup
aws s3 cp s3://your-backup-bucket/repo-name/git_backup_2025-01-15.tar.gz ./

# Extract and verify
tar -tzf git_backup_2025-01-15.tar.gz
```

### Restore Process

1. Download backup artifacts from S3
2. Extract git repositories
3. Create new GitHub repositories
4. Push git mirrors to new repositories
5. Import metadata using GitHub API

## 📈 Cost Optimization

### Storage Lifecycle

- **Standard**: First 90 days (~$0.023/GB/month)
- **Deep Archive**: After 90 days (~$0.00099/GB/month)

### Compute Costs

- Weekly execution: ~$0.20/month for small organizations
- Container reuse reduces cold starts
- Memory allocation optimized for performance vs. cost

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [Architecture Guide](./ARCHITECTURE.md)
- **Issues**: [GitHub Issues](https://github.com/your-org/github-backup/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/github-backup/discussions)

## 🏷️ Version History

- **v1.0.0** - Initial release with basic backup functionality
- **v1.1.0** - Added wiki backup support
- **v1.2.0** - Implemented lifecycle management and cost optimization

---

**⚠️ Important**: Ensure your GitHub token has appropriate permissions for all repositories in your organization. Test with a small organization first before deploying to production.