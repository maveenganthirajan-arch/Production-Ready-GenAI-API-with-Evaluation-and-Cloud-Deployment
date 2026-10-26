<#
==============================================================================
PowerShell AWS ECS Fargate Automated Deployment Script
==============================================================================
#>

param (
    [string]$AwsRegion = "us-east-1",
    [string]$StackName = "genai-rag-production",
    [string]$EcrRepoName = "enterprise-genai-rag",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Deploying Enterprise GenAI RAG Application to AWS ECS Fargate" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. AWS Account ID
$accountId = aws sts get-caller-identity --query Account --output text
$ecrUri = "$accountId.dkr.ecr.$AwsRegion.amazonaws.com/$EcrRepoName"

# 2. Check ECR repo
Write-Host "[1/4] Ensuring ECR Repository exists..." -ForegroundColor Yellow
aws ecr describe-repositories --repository-names $EcrRepoName --region $AwsRegion 2>$null
if ($LASTEXITCODE -ne 0) {
    aws ecr create-repository --repository-name $EcrRepoName --region $AwsRegion
}

# 3. Docker build & push
Write-Host "[2/4] Authenticating & pushing Docker image to ECR..." -ForegroundColor Yellow
aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin $ecrUri
docker build -t "$ecrUri`:$ImageTag" .
docker push "$ecrUri`:$ImageTag"

# 4. CloudFormation Deploy
Write-Host "[3/4] Deploying CloudFormation Stack (VPC, ALB, ECS, IAM, Secrets)..." -ForegroundColor Yellow
aws cloudformation deploy `
    --template-file infra/aws/ecs-fargate.yml `
    --stack-name $StackName `
    --capabilities CAPABILITY_IAM `
    --parameter-overrides EnvironmentName="production" ContainerImage="$ecrUri`:$ImageTag" ApiKeySecretValue="sk-enterprise-rag-prod-secret-key-2026" `
    --region $AwsRegion

$albDns = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDNS'].OutputValue" `
    --output text `
    --region $AwsRegion

Write-Host "=================================================================" -ForegroundColor Green
Write-Host " AWS Deployment Succeeded!" -ForegroundColor Green
Write-Host " URL: http://$albDns" -ForegroundColor Green
Write-Host " Swagger: http://$albDns/docs" -ForegroundColor Green
Write-Host " Dashboard: http://$albDns/dashboard" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green
