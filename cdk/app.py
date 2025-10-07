#!/usr/bin/env python3
import aws_cdk as cdk
from cdk_stack import DashboardStack

app = cdk.App()

# Prod/dev stack (normal behavior; endpoints toggle can also be set via -c includeEcsControlEndpoints=true/false)
DashboardStack(app, "DashboardStack")

# Optional test stack to validate cost changes (ECS ctrl-plane endpoints disabled)
# Not deployed unless we target it explicitly:
#   npx cdk@2 deploy DashboardStackTest -c includeEcsControlEndpoints=false --require-approval never
DashboardStack(app, "DashboardStackTest", include_ecs_control_endpoints=False)

app.synth()
