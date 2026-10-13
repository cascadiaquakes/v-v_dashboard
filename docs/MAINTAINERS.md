# Maintainer Notes

Operational details for people who deploy and administer the V&V dashboard. For an overview, see the [README](../README.md).

## One-time AWS/ECR login (for manual builds)

```bash
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws ecr get-login-password --region "$AWS_REGION" \
| docker login --username AWS --password-stdin \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
```

After that, you can run `cdk synth/deploy` locally if needed.

## Verify a deployment (smoke test)

The deploy workflow already curls the ALB and the status API. You can also fetch the live URLs from CloudFormation outputs:

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

**Networking check:** in **CloudFormation → Outputs**, `EndpointMode` should be `public-ip` for the cost-optimized main stack. In **VPC → Endpoints**, you should only see the **S3 Gateway** endpoint for the stack VPC (no ECS/ECR/Logs interface endpoints).

## Destroy an environment

**Preferred:** run **Actions → destroy-dev** (or **destroy-prod** for production) and type the confirmation phrase shown in the input.
**Alternative:** delete the stack from the **CloudFormation** console.

> **Warning:** destroying removes the stack resources. Only run it when you truly want the stack gone.

## Networking and costs

* The **main stack** defaults to **public-ip** mode: tasks get public IPs in public subnets; only the **S3 Gateway** endpoint is created. This avoids hourly charges from ECS/ECR/Logs **interface endpoints**.
* If you ever need the private interface endpoints again, flip the flag in `cdk/app.py` (`include_ecs_private_endpoints=True`) and redeploy.
