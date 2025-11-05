import json
import os
import boto3

SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

sns_client = boto3.client('sns')
secrets_client = boto3.client('secretsmanager')

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        order_id = body.get('order_id')
        amount_total = body.get('amount_total')
        api_key = body.get('api_key')

        api_key_response = secrets_client.get_secret_value(SecretId="API_KEY")

        if api_key != api_key_response['SecretString']:
            return {
                'statusCode': 403,
                'body': json.dumps({'message': 'Forbidden: Invalid API key.'})
            }

        if not all([order_id, amount_total]):
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing required fields.'})
            }

        message = {
            'order_id': order_id,
            'amount_total': amount_total
        }

        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps({'default': json.dumps(message)}),
            MessageStructure='json'
        )
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Webhook received and published successfully.'})
        }
    except Exception as e:
        print(f"ERROR: Failed to publish to SNS: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error while publishing event.'})
        }
