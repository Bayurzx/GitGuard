# Dockerfile for Lambda container
FROM public.ecr.aws/lambda/python:3.12

# Install git
RUN microdnf update -y && \
    microdnf install -y git tar && \
    microdnf clean all

# Copy requirements.txt
# ${LAMBDA_TASK_ROOT} is /var/task and is gotten from `public.ecr.aws/lambda/python:3.12` 
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install the specified packages
RUN pip install -r requirements.txt

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Environment variables
ENV HOME=/tmp
ENV GITHUB_ORG="Iglumtechnologies"
ENV S3_BUCKET="iglumtech-gh-backup"
ENV SECRET_NAME="github-backup-credentials"

# Command to run the Lambda handler
CMD [ "lambda_function.lambda_handler" ]