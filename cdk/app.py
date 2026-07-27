import os

import aws_cdk as cdk
from cdk_stack import DashboardStack
from dev_ecs_stack import DashboardDevEcsStack

app = cdk.App()

# dynamic image tags from CI (context first, then env)
app_tag = app.node.try_get_context("appTag") or os.getenv("APP_IMAGE_TAG")
lambda_tag = app.node.try_get_context("lambdaTag") or os.getenv("LAMBDA_IMAGE_TAG")

# --- Main stack (new cost-optimized behavior) ---
DashboardStack(
    app,
    "DashboardStack",
    include_ecs_private_endpoints=False,  # endpoints OFF to save cost
    app_image_tag=app_tag,
    lambda_image_tag=lambda_tag,
)

# --- Test stack: endpoints OFF (use public IP on tasks; no NAT/endpoints needed) ---
DashboardStack(
    app,
    "DashboardStackTest",
    include_ecs_private_endpoints=False,  # remove ECS/ECR control-plane endpoints
    app_image_tag=app_tag,
    lambda_image_tag=lambda_tag,
)

# App-only development stack. It is intentionally conditional so ordinary
# synths do not require AWS lookups or create another deployment by default.
production_vpc_id = app.node.try_get_context("productionVpcId")
production_cluster_name = app.node.try_get_context("productionClusterName")
production_public_subnet_ids = app.node.try_get_context("productionPublicSubnetIds")
production_availability_zones = app.node.try_get_context("productionAvailabilityZones")
if (
    production_vpc_id
    and production_cluster_name
    and production_public_subnet_ids
    and production_availability_zones
    and app_tag
):
    DashboardDevEcsStack(
        app,
        "DashboardEcsDev",
        env=cdk.Environment(
            account=os.getenv("CDK_DEFAULT_ACCOUNT"),
            region=os.getenv("CDK_DEFAULT_REGION"),
        ),
        production_vpc_id=production_vpc_id,
        production_cluster_name=production_cluster_name,
        production_public_subnet_ids=production_public_subnet_ids.split(","),
        production_availability_zones=production_availability_zones.split(","),
        app_image_tag=app_tag,
    )

app.synth()
