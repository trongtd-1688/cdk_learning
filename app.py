#!/usr/bin/env python3
import os
import aws_cdk as cdk
from order_processing_stack.order_processing_stack import OrderProcessingStack

account = os.environ.get("CDK_DEFAULT_ACCOUNT")
region = os.environ.get("CDK_DEFAULT_REGION")
env = cdk.Environment(account=account, region=region)

app = cdk.App()

OrderProcessingStack(app, "OrderProcessingStack", env=env)

app.synth()
