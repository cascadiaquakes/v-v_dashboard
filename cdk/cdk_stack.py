from aws_cdk import (
    Stack,
    Duration,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_events_targets as targets,
    aws_events as events,
    aws_apigateway as apigateway,
    CfnOutput,
)
from constructs import Construct


class DashboardStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        include_ecs_private_endpoints: bool = True,
        app_image_tag: str | None = None,
        lambda_image_tag: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # VPC without NAT (keep existing layout)
        vpc = ec2.Vpc(
            self,
            "DashboardVPC",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24
                ),
            ],
        )

        # Always: S3 gateway endpoint (cheap, needed for S3 access without NAT)
        vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        # Optional private interface endpoints (costly) – toggle via flag
        if include_ecs_private_endpoints:
            vpc.add_interface_endpoint(
                "EcsEndpoint",
                service=ec2.InterfaceVpcEndpointAwsService.ECS,
            )
            vpc.add_interface_endpoint(
                "EcsAgentEndpoint",
                service=ec2.InterfaceVpcEndpointAwsService.ECS_AGENT,
            )
            vpc.add_interface_endpoint(
                "EcsTelemetryEndpoint",
                service=ec2.InterfaceVpcEndpointAwsService.ECS_TELEMETRY,
            )
            vpc.add_interface_endpoint(
                "EcrEndpoint",
                service=ec2.InterfaceVpcEndpointAwsService.ECR,
            )
            vpc.add_interface_endpoint(
                "EcrDockerEndpoint",
                service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            )
            vpc.add_interface_endpoint(
                "LogsEndpoint",
                service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            )

        # ECS cluster
        cluster = ecs.Cluster(self, "DashboardCluster", vpc=vpc)

        # ECR repos
        repository = ecr.Repository.from_repository_name(
            self, "VVDashboardRepo", "v-v_dashboard"
        )
        lambda_repo = ecr.Repository.from_repository_name(
            self, "VvLambdaUploadRepo", repository_name="vv-lambda-upload"
        )

        # Existing S3 bucket
        s3_bucket = s3.Bucket.from_bucket_name(
            self, "BenchmarkDataBucket", bucket_name="benchmark-vv-data"
        )

        # Task role
        task_role = iam.Role(
            self,
            "DashboardTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                ),
            ],
        )
        s3_bucket.grant_read(task_role, "public_ds/*")
        s3_bucket.grant_read(task_role, "benchmark_templates/*")

        # Task definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "DashboardTaskDef",
            memory_limit_mib=12288,
            cpu=2048,
            execution_role=task_role,
            task_role=task_role,
        )

        # App container – use dynamic tag if provided
        container = task_definition.add_container(
            "DashboardContainer",
            image=ecs.ContainerImage.from_ecr_repository(
                repository, tag_or_digest=(app_image_tag or "2.1.15")
            ),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="DashboardApp"),
        )
        container.add_port_mappings(ecs.PortMapping(container_port=8050))

        # When endpoints are OFF (no NAT), run tasks in PUBLIC subnets with public IP
        fargate_kwargs = {}
        if not include_ecs_private_endpoints:
            fargate_kwargs.update(
                dict(
                    task_subnets=ec2.SubnetSelection(
                        subnet_type=ec2.SubnetType.PUBLIC
                    ),
                    assign_public_ip=True,
                )
            )

        # Fargate Service + ALB
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "DashboardFargateService",
            cluster=cluster,
            task_definition=task_definition,
            public_load_balancer=True,
            **fargate_kwargs,
        )

        CfnOutput(
            self,
            "ServiceURL",
            value=fargate_service.load_balancer.load_balancer_dns_name,
        )

        # Lambda role
        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )

        # S3 policy bits (keep as in existing)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:ListBucket"],
                resources=["arn:aws:s3:::my-bucket"],
                conditions={"StringLike": {"s3:prefix": "upload/"}},
            )
        )
        s3_bucket.grant_read(lambda_role, "upload/*")
        s3_bucket.grant_read(lambda_role, "benchmark_templates/*")
        s3_bucket.grant_put(lambda_role, "public_ds/*")

        # DynamoDB (existing table)
        table = dynamodb.Table.from_table_name(
            self, "DETFileProcessingStatusTable", table_name="DETFileProcessingStatus"
        )
        table.grant_read_write_data(lambda_role)

        # Lambda from ECR – use dynamic tag if provided
        process_uploads = _lambda.DockerImageFunction(
            self,
            "ProcessUploadsLambda",
            function_name="process_uploads",
            code=_lambda.DockerImageCode.from_ecr(
                repository=lambda_repo,
                tag_or_digest=(lambda_image_tag or "2.0.17"),
            ),
            timeout=Duration.minutes(8),
            memory_size=8192,
            environment={"TABLE_NAME": table.table_name},
            role=lambda_role,
        )

        # Failure handler lambda
        notify_fail = _lambda.Function(
            self,
            "NotifyFailLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
import json
import os
import boto3

s3 = boto3.client("s3")

def handler(event, context):
    try:
        print("Raw failure event:", json.dumps(event))
        s3_detail = event.get("s3Event", {}).get("detail", {})
        bucket = s3_detail.get("bucket", {}).get("name", "unknown")
        key = s3_detail.get("object", {}).get("key", "unknown")
        response = s3.head_object(Bucket=bucket, Key=key)
        user_metadata = response.get('Metadata', {})
        user_id = user_metadata.get("userid")
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(os.environ["TABLE_NAME"])
        table.update_item(
            Key={"userId": user_id, "fileId": os.path.basename(key)},
            UpdateExpression="SET #s = :s, #e = :e",
            ExpressionAttributeNames={"#s": "status", "#e": "error"},
            ExpressionAttributeValues={":s": "failed", ":e": event.get("error", "Timeout during processing")}
        )
        return {"status": "failure_recorded"}
    except Exception as e:
        print(f"CRITICAL: Failure handler failed: {str(e)}")
        raise
                """
            ),
            timeout=Duration.seconds(20),
            memory_size=512,
            environment={"TABLE_NAME": table.table_name},
        )
        s3_bucket.grant_read(notify_fail)
        table.grant_write_data(notify_fail)

        # Step Functions flow
        store_event_step = sfn.Pass(
            self, "StoreOriginalEvent", parameters={"originalEvent": sfn.JsonPath.entire_payload}
        )
        process_task = tasks.LambdaInvoke(
            self,
            "ProcessFile",
            lambda_function=process_uploads,
            payload=sfn.TaskInput.from_object(
                {"s3Event": sfn.JsonPath.string_at("$.originalEvent")}
            ),
            result_path="$.lambdaResult",
        )
        handle_failure_task = tasks.LambdaInvoke(
            self,
            "HandleFailure",
            lambda_function=notify_fail,
            payload=sfn.TaskInput.from_object(
                {
                    "s3Event": sfn.JsonPath.string_at("$.originalEvent"),
                    "error": sfn.JsonPath.string_at("$.errorInfo.Error"),
                }
            ),
        )
        definition = store_event_step.next(
            process_task.add_catch(
                handle_failure_task, errors=["States.ALL"], result_path="$.errorInfo"
            )
        )
        state_machine = sfn.StateMachine(
            self, "FileProcessingStateMachine", definition=definition, timeout=Duration.minutes(10)
        )
        process_uploads.grant_invoke(state_machine)
        notify_fail.grant_invoke(state_machine)

        # EventBridge rule for S3 upload
        rule = events.Rule(
            self,
            "S3UploadRule",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created", "Object Updated"],
                detail={
                    "bucket": {"name": [s3_bucket.bucket_name]},
                    "object": {"key": [{"prefix": "upload/"}]},
                },
            ),
        )
        rule.add_target(targets.SfnStateMachine(state_machine))

        # Status check lambda + API
        status_check_lambda = _lambda.Function(
            self,
            "StatusCheckLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("./lambda_status_check"),
            environment={"TABLE_NAME": table.table_name},
            timeout=Duration.seconds(10),
            memory_size=256,
            role=lambda_role,
        )
        table.grant_read_data(status_check_lambda)

        api = apigateway.RestApi(
            self,
            "FileStatusAPI",
            default_cors_preflight_options={
                "allow_origins": ["https://det-uploader.cascadiaquakes.org"],
                "allow_methods": ["GET", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
            },
        )
        status_resource = api.root.add_resource("status")
        status_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(status_check_lambda),
            authorization_type=apigateway.AuthorizationType.NONE,
        )

        CfnOutput(
            self,
            "StatusAPIHealthURL",
            value=f"{api.url}status",
            description="Endpoint for checking processing status",
        )

        CfnOutput(
            self,
            "EndpointMode",
            value="private-endpoints" if include_ecs_private_endpoints else "public-ip",
        )
