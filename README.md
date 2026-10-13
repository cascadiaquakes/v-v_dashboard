# v-v_dashboard (DET Viewer)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18778323.svg)](https://doi.org/10.5281/zenodo.18778323)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE)

Dash app and AWS CDK stack for the results dashboard of the CRESCENT Dynamic Rupture, Earthquake Cycle, and Tsunami (DET) Code Verification Platform. Results are uploaded through the [DET File Manager](https://github.com/cascadiaquakes/det-file-manager).

**Live dashboard:** https://det.cascadiaquakes.org

---

## Documentation

The platform is described in Bachelot et al. (2026), [*CRESCENT Earthquake Dynamic Rupture, Earthquake Cycle, and Tsunami Code Verification Platform*](https://doi.org/10.26443/seismica.v5i2.2716), *Seismica*.

---

## Features

- Choose a benchmark or view project information.
- Select the uploaded datasets to compare.
- Interactive comparison plots with graph controls.

---

## Architecture

The Dash web app runs on **ECS Fargate** behind an **ALB**, exposes a small **API Gateway** endpoint for status checks, and invokes a **Lambda (container image)** during uploads. Data lives in an existing **S3 bucket** and **DynamoDB** table.

**Stacks:**
- **`DashboardStack`**: production. Runs in **public-ip** mode to minimize cost (no ECS/ECR/Logs interface endpoints; only S3 gateway endpoint).
- **`DashboardEcsDev`**: app-only dev stack that reuses the production VPC, cluster and subnets, for checking changes before they reach production.

---

## Running Locally

**Prerequisites**

* Docker (with `buildx`)
* AWS CLI v2
* Python 3.9+
* Node.js 20+ and CDK v2 (`npm i -g aws-cdk`)

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
pip install -r cdk/requirements.txt
```

To build images or run `cdk synth/deploy` from your machine, see the ECR login steps in [docs/MAINTAINERS.md](docs/MAINTAINERS.md).

---

## Project Structure

```
v-v_dashboard/
├── app_dev.py / app_prod.py   # Dash app entry points
├── app_layout.py              # Page layout and controls
├── callbacks/                 # Dash callbacks and plotting
├── lambda_process_uploads/    # Lambda (container image) that processes uploads
├── lambda_status_check/       # Status API Lambda
├── cdk/                       # CDK app: DashboardStack and DashboardEcsDev
├── assets/                    # Logos and static assets
├── docs/MAINTAINERS.md        # Smoke tests, teardown, networking and costs
├── .github/workflows/         # CI and deploy workflows
└── Dockerfile
```

---

## Deployment

GitHub Actions deploys to **us-west-2** using AWS **OIDC** (no stored keys).

| Workflow | Trigger | What it does |
|---|---|---|
| `ci` | PRs to `main` | Ruff lint, pytest, and quick Docker build checks |
| `deploy-dev` | Push to `main` (or manual) | Builds the image and deploys `DashboardEcsDev` |
| `deploy-prod` | Manual, needs an approval on the `production` environment | Builds and pushes the app and Lambda images, deploys `DashboardStack`, then smoke-tests it |
| `destroy-dev` | Manual, type `DESTROY DashboardEcsDev` to confirm | Tears down the dev stack |
| `destroy-prod` | Manual, approval plus typing `DESTROY DashboardStack` to confirm | Tears down production |

**To deploy:**
1. Open a PR into `main`. CI runs on it.
2. Merge. `deploy-dev` deploys the change to `DashboardEcsDev` automatically.
3. Check the dev stack, then go to **Actions → deploy-prod → Run workflow** on `main`. A reviewer on the `production` environment approves it before it runs.

The commit SHA is passed to CDK for both ECS and Lambda, keeping images in sync. Smoke tests, teardown and networking/cost notes are in [docs/MAINTAINERS.md](docs/MAINTAINERS.md).

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
      <img src="https://raw.githubusercontent.com/cascadiaquakes/.github/main/assets/crescent-circle.png" alt="CRESCENT Logo" width="150" />
    </td>
    <td align="center" valign="middle">
      <img src="https://raw.githubusercontent.com/cascadiaquakes/.github/main/assets/nsf-logo.png" alt="NSF Logo" width="450" />
    </td>
  </tr>
</table>

This project is supported by the National Science Foundation through the Cascadia Region Earthquake Science Center (CRESCENT), Cooperative Agreement EAR-2225286.
