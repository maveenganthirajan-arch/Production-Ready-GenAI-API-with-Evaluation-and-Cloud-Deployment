# Cloud Deployment Guide: Azure & AWS

This step-by-step runbook explains how to deploy the containerized GenAI RAG Application to either **Azure Container Apps** or **Amazon ECS Fargate**.

---

## Option A: Deploy to Azure Container Apps (Recommended)

### Prerequisites
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed and logged in (`az login`).
- Docker installed locally (or Azure ACR remote build).

### Step 1: Run the Automated Deployment Script
**Linux / macOS (Bash):**
```bash
chmod +x deploy/deploy_azure.sh
./deploy/deploy_azure.sh v1.0.0
```

**Windows (PowerShell):**
```powershell
.\deploy\deploy_azure.ps1 -ImageTag "v1.0.0"
```

### Step 2: What the Script Does Automatically
1. Creates an Azure Resource Group (`rg-genai-prod`).
2. Provisions infrastructure via Bicep template `infra/azure/main.bicep`:
   - Azure Container Registry (`genairagprodacr`)
   - Log Analytics Workspace (`genai-rag-prod-logs`)
   - Azure Key Vault (`genairagprodkv`) storing the production `API_KEY`
   - User-Assigned Managed Identity with `AcrPull` permissions
   - Container Apps Managed Environment with external ingress
3. Builds and pushes the Docker container to ACR.
4. Updates the Container App with the new revision.
5. Verifies the `/health` endpoint and outputs the live public URL.

---

## Option B: Deploy to Amazon ECS Fargate

### Prerequisites
- [AWS CLI](https://aws.amazon.com/cli/) configured (`aws configure`).
- Docker installed and running.

### Step 1: Run the Automated Deployment Script
**Linux / macOS (Bash):**
```bash
chmod +x deploy/deploy_aws.sh
./deploy/deploy_aws.sh v1.0.0
```

**Windows (PowerShell):**
```powershell
.\deploy\deploy_aws.ps1 -ImageTag "v1.0.0"
```

### Step 2: What the Script Does Automatically
1. Authenticates Docker to Amazon ECR.
2. Builds and pushes the image to ECR.
3. Deploys CloudFormation stack `infra/aws/ecs-fargate.yml`:
   - Custom VPC with public subnets and Internet Gateway
   - Application Load Balancer (ALB) with listener on port 80
   - ECS Task Definition (Fargate, 0.5 vCPU, 1 GB RAM)
   - AWS Secrets Manager secret for `API_KEY`
   - CloudWatch log group `/ecs/production-genai-rag`
   - ECS Service with 2 desired tasks and auto-recovery
4. Outputs the public ALB DNS URL.

---

## Option C: Local Docker Compose

To test the container stack locally:
```bash
docker compose up -d --build
```
Verify the service is running:
```bash
curl http://localhost:8000/health
```
Access the interactive dashboard in your browser:
```
http://localhost:8000/dashboard
```
View the Swagger OpenAPI documentation:
```
http://localhost:8000/docs
```
Stop the container stack:
```bash
docker compose down
```
