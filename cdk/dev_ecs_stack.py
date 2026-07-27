from aws_cdk import (
    CfnOutput,
    Stack,
    Tags,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_ecr as ecr,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from aws_cdk import (
    aws_ecs_patterns as ecs_patterns,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_s3 as s3,
)
from constructs import Construct


class DashboardDevEcsStack(Stack):
    """App-only test service that reuses production shared infrastructure."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        production_vpc_id: str,
        production_cluster_name: str,
        production_public_subnet_ids: list[str],
        production_availability_zones: list[str],
        app_image_tag: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_vpc_attributes(
            self,
            "ProductionVpc",
            vpc_id=production_vpc_id,
            availability_zones=production_availability_zones,
            public_subnet_ids=production_public_subnet_ids,
        )
        cluster = ecs.Cluster.from_cluster_attributes(
            self,
            "ProductionCluster",
            cluster_name=production_cluster_name,
            vpc=vpc,
        )

        repository = ecr.Repository.from_repository_name(
            self,
            "VVDashboardRepo",
            repository_name="v-v_dashboard",
        )
        benchmark_bucket = s3.Bucket.from_bucket_name(
            self,
            "BenchmarkDataBucket",
            bucket_name="benchmark-vv-data",
        )

        execution_role = iam.Role(
            self,
            "DevTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )
        task_role = iam.Role(
            self,
            "DevTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        benchmark_bucket.grant_read(task_role, "public_ds/*")
        benchmark_bucket.grant_read(task_role, "benchmark_templates/*")

        task_definition = ecs.FargateTaskDefinition(
            self,
            "DevDashboardTaskDef",
            memory_limit_mib=12288,
            cpu=2048,
            execution_role=execution_role,
            task_role=task_role,
        )
        container = task_definition.add_container(
            "DevDashboardContainer",
            image=ecs.ContainerImage.from_ecr_repository(
                repository,
                tag=app_image_tag,
            ),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="DashboardAppDev"),
        )
        container.add_port_mappings(ecs.PortMapping(container_port=8050))

        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "DevDashboardService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            min_healthy_percent=100,
            max_healthy_percent=200,
            public_load_balancer=True,
            task_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC,
            ),
            assign_public_ip=True,
        )

        Tags.of(self).add("Environment", "development")
        Tags.of(self).add("Application", "v-v-dashboard")

        CfnOutput(
            self,
            "ServiceURL",
            value=service.load_balancer.load_balancer_dns_name,
            description="Public DNS name of the isolated development dashboard",
        )
