# v-v_dashboard (DET Viewer)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18778323.svg)](https://doi.org/10.5281/zenodo.18778323)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE)

**Live dashboard:** https://det.cascadiaquakes.org

Dash app + AWS CDK stack for the DET “viewer”.

**What it does:** serves a Dash web app on **ECS Fargate** behind an **ALB**, exposes a small **API Gateway** endpoint for status checks, and invokes a **Lambda (container image)** during uploads. Data lives in an existing **S3 bucket** and **DynamoDB** table.

**Stacks provided:**
- **`DashboardStack`**: production. Runs in **public-ip** mode to minimize cost (no ECS/ECR/Logs interface endpoints; only S3 gateway endpoint).
- **`DashboardEcsDev`**: app-only dev stack that reuses the production VPC, cluster and subnets, for checking changes before they reach production.

---

## Platform reference

The platform is described in Bachelot et al., [*CRESCENT Earthquake Dynamic Rupture, Earthquake Cycle, and Tsunami Code Verification Platform*](https://seismica.library.mcgill.ca/article/view/2716), *Seismica*. DOI: [10.26443/seismica.v5i2.2716](https://doi.org/10.26443/seismica.v5i2.2716).

---

## CI/CD Pipeline

This repo ships with **GitHub Actions**. Deploys are pinned to **us-west-2** and use AWS **OIDC** (no stored keys).

| Workflow | Trigger | What it does |
|---|---|---|
| `ci` | PRs to `main` | Ruff lint, pytest, and quick Docker build checks |
| `deploy-dev` | Push to `main` (or manual) | Builds the image and deploys `DashboardEcsDev` |
| `deploy-prod` | Manual, needs an approval on the `production` environment | Builds and pushes the app and Lambda images, deploys `DashboardStack`, then smoke-tests it |
| `destroy-dev` | Manual, type `DESTROY DashboardEcsDev` to confirm | Tears down the dev stack |
| `destroy-prod` | Manual, approval plus typing `DESTROY DashboardStack` to confirm | Tears down production |

**Dynamic image tags:** the commit SHA is passed to CDK for both ECS and Lambda, keeping images in sync.

---

## How to Deploy

1. Open a PR into `main`. CI runs on it.
2. Merge. `deploy-dev` deploys the change to `DashboardEcsDev` automatically.
3. Check the dev stack, then go to **Actions → deploy-prod → Run workflow** on `main`. A reviewer on the `production` environment approves it before it runs.

---

## Verify the deployment (Smoke Test)

The workflow already curls the ALB and the status API. You can also fetch the live URLs from CloudFormation outputs:

```bash
STACK="DashboardStack"   # or DashboardEcsDev
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

**Preferred:** run **Actions → destroy-dev** (or **destroy-prod** for production) and type the confirmation phrase shown in the input.
**Alternative:** delete the stack from the **CloudFormation** console.

> **Warning:** destroying removes the stack resources. Only run it when you truly want the stack gone.

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
## How to Cite

> Bachelot, L., & Marfo, W. (2026). *Verification and Validation (V&V) Dashboard* (v1.0.1). Zenodo. https://doi.org/10.5281/zenodo.18778323

The platform is described in:

> Bachelot, L., Kutschera, F., Barall, M., Erickson, B. A., Dunham, E. M., Gabriel, A.-A., Harris, R., Ma, S., Thomas, A. M., & Zhang, W. (2026). CRESCENT Earthquake Dynamic Rupture, Earthquake Cycle, and Tsunami Code Verification Platform. *Seismica*, 5(2). https://doi.org/10.26443/seismica.v5i2.2716

---

## License

This project is licensed under the BSD 3-Clause License. See [LICENSE](LICENSE).

---

## Contacts

- **Loïc Bachelot**, University of Oregon: [lbachelo@uoregon.edu](mailto:lbachelo@uoregon.edu)
- **William Marfo**, University of California, Davis: [wmarfo@ucdavis.edu](mailto:wmarfo@ucdavis.edu)
- **Amanda M. Thomas**, University of California, Davis: [amthom@ucdavis.edu](mailto:amthom@ucdavis.edu)

For bugs or feature requests, please [open an issue](https://github.com/cascadiaquakes/v-v_dashboard/issues).

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

CRESCENT is funded by NSF Cooperative Agreement EAR-2225286 and is also supported by the Pacific Gas and Electric Company (PG&E).
