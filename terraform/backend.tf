# backend.tf
terraform {
  backend "s3" {
    bucket = "iglumtech-terraform-state-bucket"
    key    = "backup-gh/terraform.tfstate"
    region = "us-east-1"
  }
}
