# v-v_dashboard (DET Viewer)

Dash app + AWS CDK stack for the DET “viewer”.

**What it does:** serves a Dash web app on **ECS Fargate** behind an **ALB**, exposes a small **API Gateway** endpoint for status checks, and invokes a **Lambda (container image)** during uploads. Data lives in an existing **S3 bucket** and **DynamoDB** table.

**Stacks provided:**
- **`DashboardStack`** — main environment (default). Runs in **public-ip** mode to minimize cost (no ECS/ECR/Logs interface endpoints; only S3 gateway endpoint).
- **`DashboardStackTest`** — optional test stack to validate changes safely. Use for experiments, then destroy to avoid cost.

---

## CI/CD Pipeline (Recommended)

This repo ships with **GitHub Actions**. Deploys are pinned to **us-west-2** and the workflow updates an existing stack.

### CI (Continuous Integration)
- **Trigger:** pushes to `ci/test` and PRs to `main`.
- **Actions:** Ruff lint, pytest, and quick Docker build sanity checks.

### CD (Continuous Delivery)
- **Trigger:**
  - Automatically on pushes to `ci/test`, **or**
  - Manually via **Actions → deploy-dev → Run workflow** (choose a branch, typically `main`).
- **What it does:** Uses AWS **OIDC** (no stored keys), builds & pushes the app and Lambda images to **ECR (us-west-2)**, deploys with **CDK**, then smoke-tests the ALB and status API.
- **Inputs (manual runs):**
  - **Image tag** (optional): defaults to the commit SHA.
  - **Stack**: `DashboardStack` *(default)* or `DashboardStackTest`.

> The workflow exposes `DEPLOY_REGION` and is locked to `us-west-2`.

---

## How to Deploy

### Option A — Push to the CI branch (auto)
```bash
git push origin ci/test
````

This triggers CI and then deploys **`DashboardStack`** with the commit SHA as the image tag.

### Option B — Run it manually

1. Go to **Actions → deploy-dev**.
2. Click **Run workflow**.
3. Choose **Branch: main** (or another branch you want).
4. (Optional) Set **Image tag**; otherwise it uses the commit SHA.
5. Set **Stack** to deploy: `DashboardStack` or `DashboardStackTest`.
6. Run and follow the logs.

**Dynamic image tags:** the commit SHA is passed to CDK for both ECS and Lambda, keeping images in sync.

---

## Verify the deployment (Smoke Test)

The workflow already curls the ALB and the status API. You can also fetch the live URLs from CloudFormation outputs:

```bash
STACK="DashboardStack"   # or DashboardStackTest
REGION="us-west-2"

ALB_URL=$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ServiceURL'].OutputValue" --output text)

API_URL=$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='StatusAPIHealthURL'].OutputValue" --output text)

echo "--- ALB: $ALB_URL"
curl -fsS "$ALB_URL" | head -n 10

echo "--- API: $API_URL"
curl -fsS "$API_URL"
```

**Networking check:** In **CloudFormation → Outputs**, `EndpointMode` should be `public-ip` for the cost-optimized main stack. In **VPC → Endpoints**, you should only see the **S3 Gateway** endpoint for the stack VPC (no ECS/ECR/Logs interface endpoints).

---

## Destroy the environment (when you’re done)

**Preferred:** run **Actions → destroy-dev → Run workflow** and set the **Stack to destroy** (e.g., `DashboardStackTest`).
**Alternative:** delete the stack from the **CloudFormation** console.

> ⚠️ Destroying removes the stack resources. Only run it when you truly want the stack gone.

---

## Local Development Setup

**Prereqs**

* Docker (with `buildx`)
* AWS CLI v2
* Python 3.9+
* Node.js 20+ and CDK v2 (`npm i -g aws-cdk`)

### 1) Python env & deps

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
pip install -r cdk/requirements.txt
```

### 2) One-time AWS/ECR login (for manual builds)

```bash
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws ecr get-login-password --region "$AWS_REGION" \
| docker login --username AWS --password-stdin \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
```

After that, you can run `cdk synth/deploy` locally if needed.

---

## Notes on networking & costs

* **Main stack** defaults to **public-ip** mode: tasks get public IPs in public subnets; only the **S3 Gateway** endpoint is created. This avoids hourly charges from ECS/ECR/Logs **interface endpoints**.
* If you ever need the private interface endpoints again, flip the flag in `cdk/app.py` (`include_ecs_private_endpoints=True`) and redeploy.

---
## Acknowledgments

<table>
  <tr>
    <td align="center" valign="middle">
      <img src="assets/favicon.ico" alt="CRESCENT Logo" width="150" />
    </td>
    <td align="center" valign="middle">
      <img src="assets/USNSF_Logo.png" alt="NSF Logo" width="450" />
    </td>
  </tr>
</table>

CRESCENT is funded by NSF cooperative agreement #2225286 and is also supported by the Pacific Gas and Electric Company (PG&E).
