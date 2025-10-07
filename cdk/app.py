#!/usr/bin/env python3
import os
import aws_cdk as cdk
from cdk_stack import DashboardStack

app = cdk.App()

# dynamic image tags from CI (context first, then env)
app_tag = app.node.try_get_context("appTag") or os.getenv("APP_IMAGE_TAG")
lambda_tag = app.node.try_get_context("lambdaTag") or os.getenv("LAMBDA_IMAGE_TAG")

# --- Main stack (current prod/dev behavior) ---
DashboardStack(
    app,
    "DashboardStack",
    include_ecs_private_endpoints=True,   # here we keep ECS/ECR control-plane endpoints
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

app.synth()
