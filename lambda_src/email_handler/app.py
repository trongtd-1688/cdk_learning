import json
import os
import boto3

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

ses_client = boto3.client('ses')

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")

    for record in event.get('Records', []):
        try:
            sns_message_body = json.loads(record.get('body', '{}'))
            event_str = sns_message_body.get('Message', '{}')
            event_obj = json.loads(event_str)

            order_id = event_obj.get('order_id')

            print(f"Sending email for order: {order_id} to {RECIPIENT_EMAIL}")

            # Gửi email qua SES
            response = ses_client.send_email(
                Source=SENDER_EMAIL,
                Destination={
                    'ToAddresses': [RECIPIENT_EMAIL]
                },
                Message={
                    'Subject': {
                        'Data': f'Order Confirmation - {order_id}',
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': f'Your order {order_id} has been successfully processed.',
                            'Charset': 'UTF-8'
                        },
                        'Html': {
                            'Data': f'<html><body><h1>Order Confirmation</h1><p>Your order <strong>{order_id}</strong> has been successfully processed.</p></body></html>',
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )

            print(f"Email sent successfully. MessageId: {response['MessageId']}")
        except Exception as e:
            print(f"ERROR: Failed to process SQS record: {record.get('messageId')}. Error: {e}")
            raise e

    return {
        'statusCode': 200,
        'body': json.dumps('Email processing finished.')
    }
