#!/usr/bin/env python3
import os
import aws_cdk as cdk
from cdk_stack import DashboardStack

app = cdk.App()

# dynamic image tags (from CI via -c or env)
app_tag = app.node.try_get_context("appTag") or os.getenv("APP_IMAGE_TAG")
lambda_tag = app.node.try_get_context("lambdaTag") or os.getenv("LAMBDA_IMAGE_TAG")

# main stack: endpoints ON (current prod behavior)
DashboardStack(
    app,
    "DashboardStack",
    include_ecs_private_endpoints=True,
    app_image_tag=app_tag,
    lambda_image_tag=lambda_tag,
)

# test stack: endpoints OFF (public IP on tasks)
DashboardStack(
    app,
    "DashboardStackTest",
    include_ecs_private_endpoints=False,
    app_image_tag=app_tag,
    lambda_image_tag=lambda_tag,
)

app.synth()