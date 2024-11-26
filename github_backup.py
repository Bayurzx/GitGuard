import os
import subprocess
import requests
import json
import boto3
from datetime import datetime

# Initialize the AWS Secrets Manager client
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')  # Set your AWS region
# secret_name = "dev-iglum-gh_backup"
secret_name = "github-backup-credentials"

# Retrieve and parse secrets from AWS Secrets Manager
def get_secret(secret_name):
    try:
        secret_value = secrets_client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in secret_value:
            secret_dict = json.loads(secret_value['SecretString'])
            return secret_dict
        else:
            raise ValueError("SecretString is not available in the response.")
    except Exception as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html

        print(f"Error retrieving secret {secret_name}: {str(e)}")
        return None


secret_data = get_secret(secret_name)
if secret_data:
    # Access AWS credentials and GitHub token from the retrieved secret data
    ACCESS_KEY = secret_data.get('AWS_ACCESS_KEY_ID')
    SECRET_KEY = secret_data.get('AWS_SECRET_ACCESS_KEY')
    REGION = secret_data.get('AWS_REGION')
    GITHUB_TOKEN = secret_data.get('GITHUB_TOKEN')
else:
    raise ValueError("Failed to retrieve required secrets.")


# TODO: Complete Configuration
# OWNER = 'Iglumtechnologies'  # TODO: Organization or GitHub account name to change
# BACKUP_DIR = './backup'
# S3_BUCKET_NAME = 'infometicsz-gh-backup' # TODO: change

OWNER = 'INFOMETICS-UBA'  # TODO: Organization or GitHub account name to change
BACKUP_DIR = './backup'
S3_BUCKET_NAME = 'infometicsz-gh-backup' # TODO: change


# AWS S3 Client setup using default directly
s3_client = boto3.client(
    's3',
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION
)


# GitHub API base URL
API_BASE_URL = f'https://api.github.com/orgs/{OWNER}/repos'

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

# Create backup folder if not exists
def create_backup_folder():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

# Step 1: Backup Git Repository
def backup_git_repo(repo_url, repo_name):
    print(f"Starting Git repository backup for {repo_name}...")
    repo_path = os.path.join(BACKUP_DIR, 'git', repo_name)
    
    # If repo_path already exists, it won't raise an error; it will simply do nothing
    os.makedirs(repo_path, exist_ok=True) 
    
    repo_mirror = os.path.join(repo_path, repo_name)
    
    if os.path.exists(repo_mirror):
        print(f"Fetching latest changes for {repo_name}...")
        subprocess.run(['git', '-C', repo_mirror, 'fetch', '--all'])
    else:
        print(f"Cloning {repo_name} as a mirror...")
        subprocess.run(['git', 'clone', '--mirror', repo_url, repo_mirror])
    
    print(f"Git repository backup completed for {repo_name}.")

# Step 2: Backup Metadata
def backup_metadata(repo_name, endpoint, backup_file):
    print(f"Backing up {endpoint} for {repo_name}...")
    response = requests.get(f'{API_BASE_URL}/{repo_name}/{endpoint}', headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        backup_file_path = os.path.join(BACKUP_DIR, f'{repo_name}_{backup_file}.json')
        with open(backup_file_path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"{endpoint} backed up successfully for {repo_name}.")
    else:
        print(f"Failed to backup {endpoint} for {repo_name}: {response.status_code}, {response.text}")

# Backup key metadata such as releases, issues, pull requests
def backup_all_metadata(repo_name):
    print(f"Starting backup of metadata for {repo_name}...")
    metadata_items = [
        ('releases', 'releases'),
        ('issues', 'issues'),
        ('pulls', 'pull_requests'),
        ('collaborators', 'collaborators'),
        ('labels', 'labels'),
        ('milestones', 'milestones'),
        ('comments', 'commit_comments'),
        ('forks', 'forks'),
        ('projects', 'projects'),
        ('actions/workflows', 'actions_workflows'),
        ('actions/secrets', 'actions_secrets'),
        ('hooks', 'webhooks'),
    ]
    for endpoint, backup_file in metadata_items:
        backup_metadata(repo_name, endpoint, backup_file)
    print(f"Metadata backup completed for {repo_name}.")

# Step 3: Backup Wiki (Optional)
def backup_wiki(repo_name):
    print(f"Starting Wiki backup for {repo_name}...")
    wiki_url = f'https://github.com/{OWNER}/{repo_name}.wiki.git'
    wiki_path = os.path.join(BACKUP_DIR, 'wiki', repo_name)
    
    if not os.path.exists(wiki_path):
        os.makedirs(wiki_path)
    
    wiki_mirror = os.path.join(wiki_path, repo_name)
    
    if os.path.exists(wiki_mirror):
        print(f"Fetching latest changes for {repo_name} Wiki...")
        subprocess.run(['git', '-C', wiki_mirror, 'fetch', '--all'])
    else:
        print(f"Cloning {repo_name} Wiki...")
        subprocess.run(['git', 'clone', '--mirror', wiki_url, wiki_mirror])
    
    print(f"Wiki backup completed for {repo_name}.")

# Step 4: Upload Backup to AWS S3
def ensure_s3_bucket_exists(bucket_name):
    try:
        # Check if the bucket exists
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"S3 bucket '{bucket_name}' exists.")
    except s3_client.exceptions.ClientError:
        # If bucket does not exist, create it
        print(f"S3 bucket '{bucket_name}' does not exist. Creating bucket...")
        s3_client.create_bucket(Bucket=bucket_name)
        print(f"S3 bucket '{bucket_name}' created successfully.")


def upload_to_s3(local_path, s3_bucket, s3_key):
    try:
        s3_client.upload_file(local_path, s3_bucket, s3_key)
        print(f"Successfully uploaded {local_path} to s3://{s3_bucket}/{s3_key}")
    except Exception as e:
        print(f"Failed to upload {local_path} to S3: {str(e)}")

def upload_backup_to_s3(repo_name):
    print(f"Uploading backups for {repo_name} to S3...")
    ensure_s3_bucket_exists(S3_BUCKET_NAME)  # Ensure the bucket is created
    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    # Upload Git repository mirror
    git_repo_path = os.path.join(BACKUP_DIR, 'git', repo_name)
    if os.path.exists(git_repo_path):
        s3_key = f"{repo_name}/git_backup_{timestamp}.tar.gz"
        subprocess.run(['tar', '-czf', f'{git_repo_path}.tar.gz', '-C', git_repo_path, '.'])
        upload_to_s3(f'{git_repo_path}.tar.gz', S3_BUCKET_NAME, s3_key)
    
    # Upload metadata
    for metadata_file in os.listdir(BACKUP_DIR):
        if repo_name in metadata_file:
            s3_key = f"{repo_name}/metadata/{metadata_file}"
            upload_to_s3(os.path.join(BACKUP_DIR, metadata_file), S3_BUCKET_NAME, s3_key)
    
    # Upload Wiki (if applicable)
    wiki_repo_path = os.path.join(BACKUP_DIR, 'wiki', repo_name)
    if os.path.exists(wiki_repo_path):
        s3_key = f"{repo_name}/wiki_backup_{timestamp}.tar.gz"
        subprocess.run(['tar', '-czf', f'{wiki_repo_path}.tar.gz', '-C', wiki_repo_path, '.'])
        upload_to_s3(f'{wiki_repo_path}.tar.gz', S3_BUCKET_NAME, s3_key)
    
    print(f"Backup for {repo_name} uploaded to S3.")

# Step 5: Backup All Repositories
def backup_all_repos():
    response = requests.get(API_BASE_URL, headers=HEADERS)
    if response.status_code == 200:
        repos = response.json()
        for repo in repos:
            repo_name = repo['name']
            repo_url = repo['clone_url']
            
            backup_git_repo(repo_url, repo_name)
            backup_all_metadata(repo_name)
            backup_wiki(repo_name)
            upload_backup_to_s3(repo_name)
    else:
        print(f"Failed to fetch repositories: {response.status_code}, {response.text}")

if __name__ == "__main__":
    create_backup_folder()
    backup_all_repos()
