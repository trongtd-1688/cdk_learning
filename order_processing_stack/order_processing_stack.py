from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_lambda as _lambda,
    aws_sns_subscriptions as subs,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_secretsmanager as secretsmanager,
    aws_cloudwatch as cloudwatch,
    aws_lambda_event_sources,
    CfnParameter,
    aws_ses as ses,
    SecretValue
)
from constructs import Construct


class OrderProcessingStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # CloudFormation Parameters
        email_sender_param = CfnParameter(self, "EmailSender",
                                          type="String",
                                          description="The email address that will send order notifications."
                                          )

        email_recipient_param = CfnParameter(self, "EmailRecipient",
                                             type="String",
                                             description="The email address that will receive order notifications."
                                             )

        api_key_value_param = CfnParameter(self, "ApiKeyValue",
                                           type="String",
                                           description="The value for the API_KEY secret."
                                           )

        # VPC with public and private subnets + NAT Gateway
        vpc = ec2.Vpc(self, "OrderProcessingVpc",
                      max_azs=1,
                      nat_gateways=1,
                      subnet_configuration=[
                          ec2.SubnetConfiguration(
                              name="public-subnet",
                              subnet_type=ec2.SubnetType.PUBLIC,
                              cidr_mask=24
                          ),
                          ec2.SubnetConfiguration(
                              name="private-subnet",
                              subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                              cidr_mask=24
                          ),
                      ]
                      )

        # DynamoDB Table
        orders_table = dynamodb.Table(self, "OrdersTable",
                                      partition_key=dynamodb.Attribute(name="PK",
                                                                       type=dynamodb.AttributeType.STRING),
                                      billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                                      removal_policy=RemovalPolicy.DESTROY
                                      )

        # SNS Topic and SQS Queues (Fan-out pattern)
        order_events_topic = sns.Topic(self, "NewOrdersTopic",
                                       display_name="New Order Events Topic"
                                       )

        email_queue_dlq = sqs.Queue(self, "EmailQueueDLQ")
        email_queue = sqs.Queue(self, "EmailQueue",
                                visibility_timeout=Duration.seconds(60),
                                dead_letter_queue=sqs.DeadLetterQueue(
                                    max_receive_count=2,
                                    queue=email_queue_dlq
                                )
                                )

        inventory_queue_dlq = sqs.Queue(self, "InventoryQueueDLQ")
        inventory_queue = sqs.Queue(self, "InventoryQueue",
                                    visibility_timeout=Duration.seconds(60),
                                    dead_letter_queue=sqs.DeadLetterQueue(
                                        max_receive_count=2,
                                        queue=inventory_queue_dlq
                                    )
                                    )

        db_update_queue_dlq = sqs.Queue(self, "DbUpdateQueueDLQ")
        db_update_queue = sqs.Queue(self, "DbUpdateQueue",
                                    visibility_timeout=Duration.seconds(60),
                                    dead_letter_queue=sqs.DeadLetterQueue(
                                        max_receive_count=2,
                                        queue=db_update_queue_dlq
                                    )
                                    )

        order_events_topic.add_subscription(subs.SqsSubscription(email_queue))
        order_events_topic.add_subscription(subs.SqsSubscription(inventory_queue))
        order_events_topic.add_subscription(subs.SqsSubscription(db_update_queue))

        # Secrets Manager for API Key
        api_key_secret = secretsmanager.Secret(self, "ApiKeySecret",
                                               secret_name="API_KEY",
                                               secret_string_value=SecretValue.unsafe_plain_text(
                                                   api_key_value_param.value_as_string),
                                               description="API key for authenticating incoming webhooks"
                                               )

        # Create Webhook Handler Lambda
        webhook_handler_role = iam.Role(self, "WebhookHandlerRole",
                                        assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                                        managed_policies=[
                                            iam.ManagedPolicy.from_aws_managed_policy_name(
                                                "service-role/AWSLambdaBasicExecutionRole"),
                                            iam.ManagedPolicy.from_aws_managed_policy_name(
                                                "service-role/AWSLambdaVPCAccessExecutionRole")
                                        ]
                                        )
        api_key_secret.grant_read(webhook_handler_role)
        order_events_topic.grant_publish(webhook_handler_role)
        webhook_handler_lambda = _lambda.Function(self, "WebhookHandlerLambda",
                                                  runtime=_lambda.Runtime.PYTHON_3_9,
                                                  code=_lambda.Code.from_asset("lambda_src/webhook_handler"),
                                                  handler="app.lambda_handler",
                                                  vpc=vpc,
                                                  vpc_subnets=ec2.SubnetSelection(
                                                      subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                                                  role=webhook_handler_role,
                                                  environment={
                                                      "SNS_TOPIC_ARN": order_events_topic.topic_arn
                                                  }
                                                  )

        # Create Email Handler Lambda
        email_handler_role = iam.Role(self, "EmailHandlerRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                                      managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name(
                                          "service-role/AWSLambdaBasicExecutionRole"),
                                          iam.ManagedPolicy.from_aws_managed_policy_name(
                                              "service-role/AWSLambdaVPCAccessExecutionRole")])
        email_queue.grant_consume_messages(email_handler_role)

        email_handler_role.add_to_policy(iam.PolicyStatement(
            actions=["ses:SendEmail", "ses:SendRawEmail"],
            resources=["*"]
        ))

        # Verify email identities in SES Sandbox
        sender_email_identity = ses.EmailIdentity(self, "SenderEmailIdentity",
                                                  identity=ses.Identity.email(email_sender_param.value_as_string)
                                                  )

        recipient_email_identity = ses.EmailIdentity(self, "RecipientEmailIdentity2",
                                                     identity=ses.Identity.email(email_recipient_param.value_as_string)
                                                     )

        email_handler_lambda = _lambda.Function(self, "EmailHandlerLambda",
                                                runtime=_lambda.Runtime.PYTHON_3_9,
                                                code=_lambda.Code.from_asset("lambda_src/email_handler"),
                                                handler="app.lambda_handler",
                                                vpc=vpc,
                                                vpc_subnets=ec2.SubnetSelection(
                                                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                                                role=email_handler_role,
                                                environment={
                                                    "SENDER_EMAIL": email_sender_param.value_as_string,
                                                    "RECIPIENT_EMAIL": email_recipient_param.value_as_string
                                                }
                                                )
        email_handler_lambda.add_event_source(aws_lambda_event_sources.SqsEventSource(email_queue))

        # Create Inventory Handler Lambda
        inventory_handler_role = iam.Role(self, "InventoryHandlerRole",
                                          assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                                          managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name(
                                              "service-role/AWSLambdaBasicExecutionRole"),
                                              iam.ManagedPolicy.from_aws_managed_policy_name(
                                                  "service-role/AWSLambdaVPCAccessExecutionRole")])
        inventory_queue.grant_consume_messages(inventory_handler_role)
        orders_table.grant_read_write_data(inventory_handler_role)

        inventory_handler_lambda = _lambda.Function(self, "InventoryHandlerLambda",
                                                    runtime=_lambda.Runtime.PYTHON_3_9,
                                                    code=_lambda.Code.from_asset("lambda_src/inventory_handler"),
                                                    handler="app.lambda_handler",
                                                    vpc=vpc,
                                                    vpc_subnets=ec2.SubnetSelection(
                                                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                                                    role=inventory_handler_role,
                                                    environment={
                                                        "ORDERS_TABLE_NAME": orders_table.table_name
                                                    }
                                                    )
        inventory_handler_lambda.add_event_source(aws_lambda_event_sources.SqsEventSource(inventory_queue))

        # Create DB Update Handler Lambda
        db_update_handler_role = iam.Role(self, "DbUpdateHandlerRole",
                                          assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                                          managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name(
                                              "service-role/AWSLambdaBasicExecutionRole"),
                                              iam.ManagedPolicy.from_aws_managed_policy_name(
                                                  "service-role/AWSLambdaVPCAccessExecutionRole")])
        db_update_queue.grant_consume_messages(db_update_handler_role)
        orders_table.grant_write_data(db_update_handler_role)

        db_update_handler_lambda = _lambda.Function(self, "DbUpdateHandlerLambda",
                                                    runtime=_lambda.Runtime.PYTHON_3_9,
                                                    code=_lambda.Code.from_asset("lambda_src/db_update_handler"),
                                                    handler="app.lambda_handler",
                                                    vpc=vpc,
                                                    vpc_subnets=ec2.SubnetSelection(
                                                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                                                    role=db_update_handler_role,
                                                    environment={
                                                        "ORDERS_TABLE_NAME": orders_table.table_name
                                                    }
                                                    )
        db_update_handler_lambda.add_event_source(aws_lambda_event_sources.SqsEventSource(db_update_queue))

        # Create API Gateway for webhook
        api = apigw.LambdaRestApi(self, "StripeWebhookApi",
                                  handler=webhook_handler_lambda,
                                  proxy=False,
                                  default_cors_preflight_options=apigw.CorsOptions(
                                      allow_origins=apigw.Cors.ALL_ORIGINS,
                                      allow_methods=apigw.Cors.ALL_METHODS
                                  )
                                  )
        webhook_resource = api.root.add_resource("webhook")
        webhook_resource.add_method("POST")

        # Add CloudWatch Alarms for DLQs
        dlq_email_alarm = cloudwatch.Alarm(self, "EmailDLQAlarm",
                                           metric=email_queue_dlq.metric("ApproximateNumberOfMessagesVisible"),
                                           threshold=0,
                                           evaluation_periods=1,
                                           comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                                           alarm_description="Alarm if there are messages in the Email DLQ",
                                           treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
                                           )

        dlq_db_update_alarm = cloudwatch.Alarm(self, "DbUpdateDLQAlarm",
                                               metric=db_update_queue_dlq.metric("ApproximateNumberOfMessagesVisible"),
                                               threshold=0,
                                               evaluation_periods=1,
                                               comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                                               alarm_description="Alarm if there are messages in the DB Update DLQ",
                                               treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
                                               )

        dlq_inventory_alarm = cloudwatch.Alarm(self, "InventoryDLQAlarm",
                                               metric=inventory_queue_dlq.metric("ApproximateNumberOfMessagesVisible"),
                                               threshold=0,
                                               evaluation_periods=1,
                                               comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                                               alarm_description="Alarm if there are messages in the Inventory DLQ",
                                               treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
                                               )
