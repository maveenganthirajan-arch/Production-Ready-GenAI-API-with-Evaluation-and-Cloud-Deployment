#!/usr/bin/env bash
# ==============================================================================
# AWS ECS Fargate Automated Deployment Script
# Provisions VPC, ALB, ECS Cluster, Task Definition, and Service via CloudFormation.
# ==============================================================================

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="genai-rag-production"
ECR_REPO_NAME="enterprise-genai-rag"
TAG="${1:-latest}"

echo "================================================================="
echo " Deploying Enterprise GenAI RAG Application to AWS ECS Fargate"
echo "================================================================="

# 1. Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

# 2. Ensure ECR Repository exists
echo "[1/5] Ensuring ECR Repository exists: ${ECR_REPO_NAME}..."
aws ecr describe-repositories --repository-names "${ECR_REPO_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1 || \
aws ecr create-repository --repository-name "${ECR_REPO_NAME}" --region "${AWS_REGION}"

# 3. Docker Login & Push to ECR
echo "[2/5] Authenticating Docker with Amazon ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_URI}"

echo "[3/5] Building and pushing Docker container image..."
docker build -t "${ECR_URI}:${TAG}" .
docker push "${ECR_URI}:${TAG}"

# 4. Deploy CloudFormation Stack
echo "[4/5] Deploying CloudFormation Stack: ${STACK_NAME}..."
aws cloudformation deploy \
  --template-file infra/aws/ecs-fargate.yml \
  --stack-name "${STACK_NAME}" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    EnvironmentName="production" \
    ContainerImage="${ECR_URI}:${TAG}" \
    ApiKeySecretValue="sk-enterprise-rag-prod-secret-key-2026" \
  --region "${AWS_REGION}"

# 5. Retrieve Load Balancer DNS
ALB_DNS=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDNS'].OutputValue" \
  --output text \
  --region "${AWS_REGION}")

echo "================================================================="
echo " AWS Deployment Complete!"
echo " Public Application ALB: http://${ALB_DNS}"
echo " Interactive API Docs: http://${ALB_DNS}/docs"
echo " Dashboard UI: http://${ALB_DNS}/dashboard"
echo " Prometheus Metrics: http://${ALB_DNS}/metrics"
echo "================================================================="
