import os
import subprocess
import requests
import json
import boto3
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Starting GitHub backup Lambda function")
    
    # Initialize the AWS Secrets Manager client
    secrets_client = boto3.client('secretsmanager')
    secret_name = os.environ['SECRET_NAME']
    logger.info(f"Retrieving secrets from {secret_name}")
    
    def get_secret(secret_name):
        try:
            secret_value = secrets_client.get_secret_value(SecretId=secret_name)
            if 'SecretString' in secret_value:
                logger.info("Successfully retrieved secret")
                return json.loads(secret_value['SecretString'])
            raise ValueError("SecretString not available")
        except Exception as e:
            logger.error(f"Error retrieving secret: {str(e)}")
            return None

    # Get secrets
    secret_data = get_secret(secret_name)
    if not secret_data:
        logger.error("Failed to retrieve required secrets")
        raise ValueError("Failed to retrieve required secrets")

    # Configure credentials
    ACCESS_KEY = secret_data.get('AWS_ACCESS_KEY_ID')
    SECRET_KEY = secret_data.get('AWS_SECRET_ACCESS_KEY')
    REGION = secret_data.get('AWS_REGION')
    GITHUB_TOKEN = secret_data.get('GITHUB_TOKEN')

    # Configuration
    OWNER = os.environ['GITHUB_ORG']
    BACKUP_DIR = '/tmp/backup'
    S3_BUCKET_NAME = os.environ['S3_BUCKET']
    
    logger.info(f"Configured for GitHub organization: {OWNER}")
    logger.info(f"Using backup directory: {BACKUP_DIR}")
    logger.info(f"Target S3 bucket: {S3_BUCKET_NAME}")

    # Set up Git credentials
    logger.info("Setting up Git credentials")
    subprocess.run(['git', 'config', '--global', 'credential.helper', 'store'])
    with open('/tmp/.git-credentials', 'w') as f:
        f.write(f'https://x-access-token:{GITHUB_TOKEN}@github.com\n')

    # AWS S3 Client setup
    s3_client = boto3.client(
        's3',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION
    )
    logger.info("AWS S3 client initialized")

    # GitHub API base URL
    API_BASE_URL = f'https://api.github.com/orgs/{OWNER}/repos'

    HEADERS = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

    def create_backup_folder():
        logger.info(f"Creating backup folder: {BACKUP_DIR}")
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
            logger.info("Backup folder created successfully")

    def backup_git_repo(repo_url, repo_name):
        logger.info(f"Starting Git repository backup for {repo_name}")
        repo_path = os.path.join(BACKUP_DIR, 'git', repo_name)
        
        os.makedirs(repo_path, exist_ok=True)
        logger.info(f"Created directory structure for {repo_name}")
        
        repo_mirror = os.path.join(repo_path, repo_name)
        
        if os.path.exists(repo_mirror):
            logger.info(f"Repository already exists, fetching latest changes for {repo_name}")
            subprocess.run(['git', '-C', repo_mirror, 'fetch', '--all'])
        else:
            logger.info(f"Cloning repository {repo_name} as mirror")
            subprocess.run(['git', 'clone', '--mirror', repo_url, repo_mirror])
        
        logger.info(f"Git repository backup completed for {repo_name}")

    def backup_metadata(repo_name, endpoint, backup_file):
        logger.info(f"Backing up {endpoint} for {repo_name}")
        response = requests.get(f'{API_BASE_URL}/{repo_name}/{endpoint}', headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            backup_file_path = os.path.join(BACKUP_DIR, f'{repo_name}_{backup_file}.json')
            with open(backup_file_path, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Successfully backed up {endpoint} for {repo_name}")
        else:
            logger.error(f"Failed to backup {endpoint} for {repo_name}: {response.status_code}, {response.text}")

    def backup_all_metadata(repo_name):
        logger.info(f"Starting metadata backup for {repo_name}")
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
        logger.info(f"Completed metadata backup for {repo_name}")

    def backup_wiki(repo_name):
        logger.info(f"Starting Wiki backup for {repo_name}")
        wiki_url = f'https://github.com/{OWNER}/{repo_name}.wiki.git'
        wiki_path = os.path.join(BACKUP_DIR, 'wiki', repo_name)
        
        if not os.path.exists(wiki_path):
            os.makedirs(wiki_path)
            logger.info(f"Created wiki directory for {repo_name}")
        
        wiki_mirror = os.path.join(wiki_path, repo_name)
        
        if os.path.exists(wiki_mirror):
            logger.info(f"Wiki already exists, fetching latest changes for {repo_name}")
            subprocess.run(['git', '-C', wiki_mirror, 'fetch', '--all'])
        else:
            logger.info(f"Cloning wiki for {repo_name}")
            subprocess.run(['git', 'clone', '--mirror', wiki_url, wiki_mirror])
        
        logger.info(f"Wiki backup completed for {repo_name}")

    def ensure_s3_bucket_exists(bucket_name):
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"S3 bucket '{bucket_name}' exists")
        except s3_client.exceptions.ClientError:
            logger.info(f"Creating S3 bucket '{bucket_name}'")
            s3_client.create_bucket(Bucket=bucket_name)
            logger.info(f"S3 bucket '{bucket_name}' created successfully")

    def upload_to_s3(local_path, s3_bucket, s3_key):
        try:
            logger.info(f"Uploading {local_path} to s3://{s3_bucket}/{s3_key}")
            s3_client.upload_file(local_path, s3_bucket, s3_key)
            logger.info(f"Successfully uploaded {local_path} to S3")
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to S3: {str(e)}")

    def upload_backup_to_s3(repo_name):
        logger.info(f"Starting S3 upload for {repo_name}")
        ensure_s3_bucket_exists(S3_BUCKET_NAME)
        timestamp = datetime.now().strftime("%Y-%m-%d")
        
        # Upload Git repository mirror
        git_repo_path = os.path.join(BACKUP_DIR, 'git', repo_name)
        if os.path.exists(git_repo_path):
            logger.info(f"Preparing Git repository archive for {repo_name}")
            s3_key = f"{repo_name}/git_backup_{timestamp}.tar.gz"
            subprocess.run(['tar', '-czf', f'{git_repo_path}.tar.gz', '-C', git_repo_path, '.'])
            upload_to_s3(f'{git_repo_path}.tar.gz', S3_BUCKET_NAME, s3_key)
        
        # Upload metadata
        logger.info(f"Uploading metadata files for {repo_name}")
        for metadata_file in os.listdir(BACKUP_DIR):
            if repo_name in metadata_file:
                s3_key = f"{repo_name}/metadata/{metadata_file}"
                upload_to_s3(os.path.join(BACKUP_DIR, metadata_file), S3_BUCKET_NAME, s3_key)
        
        # Upload Wiki
        wiki_repo_path = os.path.join(BACKUP_DIR, 'wiki', repo_name)
        if os.path.exists(wiki_repo_path):
            logger.info(f"Preparing Wiki archive for {repo_name}")
            s3_key = f"{repo_name}/wiki_backup_{timestamp}.tar.gz"
            subprocess.run(['tar', '-czf', f'{wiki_repo_path}.tar.gz', '-C', wiki_repo_path, '.'])
            upload_to_s3(f'{wiki_repo_path}.tar.gz', S3_BUCKET_NAME, s3_key)
        
        logger.info(f"Completed S3 upload for {repo_name}")

    def backup_all_repos():
        logger.info("Starting backup of all repositories")
        response = requests.get(API_BASE_URL, headers=HEADERS)
        if response.status_code == 200:
            repos = response.json()
            logger.info(f"Found {len(repos)} repositories to backup")
            for repo in repos:
                repo_name = repo['name']
                repo_url = repo['clone_url']
                
                logger.info(f"Processing repository: {repo_name}")
                backup_git_repo(repo_url, repo_name)
                backup_all_metadata(repo_name)
                backup_wiki(repo_name)
                upload_backup_to_s3(repo_name)
        else:
            logger.error(f"Failed to fetch repositories: {response.status_code}, {response.text}")

    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        create_backup_folder()
        backup_all_repos()
        
        logger.info("Backup process completed successfully")
        return {
            'statusCode': 200,
            'body': json.dumps('Backup completed successfully')
        }
    except Exception as e:
        logger.error(f"Error during backup process: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error during backup: {str(e)}')
        }